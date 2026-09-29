"""Unit 25 — leave day plan lifecycle tests.

Real rules come from the stub provider (fixed "today" = 21 Sep 2026); the
workflow chain comes from the stub workflow provider. The ``get_today`` clock
seam in the plans modules is patched to the same fixed date so confirm/lapse
windows are deterministic.
"""

from datetime import date, timedelta
from dataclasses import replace
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveType
from leave.providers.base import LeaveTypeRules
from leave.tests.stubs import TODAY, _leave_types, make_user
from notifications.models import NotificationOutbox
from users.models import EmployeeProfile, User

from .models import (
    LeaveDayPlan,
    LeavePlanBlock,
    PlanApprovalDecision,
    PlanApprovalStage,
    PlanBalanceTransaction,
)
from .services import (
    BlockStateError,
    PlanNotFoundError,
    PlanNotSubmittableError,
    PlanValidationFailedError,
    confirm_block,
    create_plan,
    decide_plan,
    lapse_overdue_blocks,
    peer_conflicts,
    release_block,
    submit_plan,
)

from leave.tests.stubs import StubProviderMixin

User = get_user_model()

SEED_PASSWORD = "testpass123"

# Plan period: fully inside FY 2026-27, well past the 5-working-day annual
# notice from TODAY (21 Sep 2026).
BLOCK_START = date(2026, 10, 6)
BLOCK_END = date(2026, 10, 9)
PLAN_START = date(2026, 10, 1)
PLAN_END = date(2026, 10, 31)


def _patch_plan_clock():
    """Pin ``get_today`` where the plans modules read it."""
    patchers = [
        mock.patch("plans.services.get_today", return_value=TODAY),
        mock.patch("plans.payloads.get_today", return_value=TODAY),
        mock.patch("notifications.plans.get_today", return_value=TODAY),
        mock.patch("plans.views.get_today", return_value=TODAY),
    ]
    for patcher in patchers:
        patcher.start()


def _profile(user, **kwargs):
    defaults = dict(
        designation="Officer",
        department="Administration",
        grade="B",
        appointment_date=date(2022, 3, 15),
        category="administration",
    )
    defaults.update(kwargs)
    return EmployeeProfile.objects.create(user=user, **defaults)


class PlanServiceBase(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        _patch_plan_clock()
        self.annual_type_id = self._sync_leave_registry()
        self.employee = make_user(
            "employee@test.luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        _profile(self.employee)
        self.stub.register_employee(self.employee)
        self.approvers = register_chain(self.stub)
        self.supervisor = self.approvers["supervisor"]
        self.hod = self.approvers["hod"]
        self.registrar = self.approvers["registrar"]
        self.dvc = self.approvers["dvc"]

    def _sync_leave_registry(self):
        """Mirror the stub's rules into the real LeaveType registry.

        ``create_plan`` verifies the registry entry exists (the rules stay with
        the stub after submission-time validation), so give each stub rule a
        real row and re-point the stub at the real primary keys.
        """
        synced = []
        for rules in _leave_types():
            leave_type = LeaveType.objects.create(name=rules.name)
            synced.append(replace(rules, id=leave_type.pk))
        self.stub.leave_types = tuple(synced)
        ann = next(r.id for r in synced if r.code == "annual")
        self.compassionate_type_id = next(r.id for r in synced if r.code == "compassionate")
        return ann

    def make_plan(self, employee=None, blocks=None, **kwargs):
        employee = employee or self.employee
        blocks = blocks or [
            {"leave_type_id": self.annual_type_id, "start_date": BLOCK_START, "end_date": BLOCK_END}
        ]
        return create_plan(
            user=employee,
            period_start=kwargs.pop("period_start", PLAN_START),
            period_end=kwargs.pop("period_end", PLAN_END),
            blocks=blocks,
        )


def register_chain(stub, roles=("supervisor", "hod", "registrar", "dvc")):
    chain = {role: make_user(f"chain-{role}@test.luanar", role=role) for role in roles}
    for role, user in chain.items():
        stub.workflow.register_approver(role, user)
    return chain


class CreatePlanTests(PlanServiceBase):
    def test_creates_draft_plan_with_blocks(self):
        plan = self.make_plan()
        self.assertEqual(plan.status, LeaveDayPlan.Status.DRAFT)
        self.assertEqual(plan.financial_year_label, "2026-27")
        self.assertEqual(plan.plan_blocks.count(), 1)
        block = plan.plan_blocks.first()
        self.assertEqual(block.status, LeavePlanBlock.Status.PROPOSED)
        self.assertEqual(block.leave_type_id, self.annual_type_id)

    def test_rejects_period_across_financial_years(self):
        with self.assertRaises(ValueError):
            self.make_plan(period_start=date(2027, 6, 1), period_end=date(2027, 7, 15))

    def test_rejects_period_before_start(self):
        with self.assertRaises(ValueError):
            self.make_plan(period_start=date(2026, 10, 20), period_end=date(2026, 10, 5))

    def test_rejects_block_ending_before_starting(self):
        with self.assertRaises(ValueError):
            self.make_plan(
                blocks=[
                    {"leave_type_id": self.annual_type_id, "start_date": date(2026, 10, 20), "end_date": date(2026, 10, 5)}
                ]
            )

    def test_rejects_unknown_leave_type(self):
        with self.assertRaises(ValueError):
            self.make_plan(blocks=[{"leave_type_id": 999, "start_date": BLOCK_START, "end_date": BLOCK_END}])

    def test_second_open_plan_same_fy_rejected(self):
        self.make_plan()
        with self.assertRaises(ValueError):
            self.make_plan()
        other = make_user("second@test.luanar", role=User.Role.EMPLOYEE)
        _profile(other)
        other_plan = create_plan(
            user=other,
            period_start=PLAN_START,
            period_end=PLAN_END,
            blocks=[{"leave_type_id": self.annual_type_id, "start_date": BLOCK_START, "end_date": BLOCK_END}],
        )
        self.assertIsNotNone(other_plan)


class SubmitPlanTests(PlanServiceBase):
    def test_submit_validates_sets_working_days_and_routes(self):
        plan = self.make_plan()
        submitted = submit_plan(user=self.employee, plan_id=plan.id)
        self.assertEqual(submitted.status, LeaveDayPlan.Status.SUBMITTED)
        block = submitted.plan_blocks.first()
        self.assertEqual(block.working_days, 4)
        stages = list(submitted.approval_stages.order_by("stage_order"))
        self.assertEqual(len(stages), 4)
        self.assertEqual(stages[0].status, PlanApprovalStage.Status.PENDING)
        self.assertEqual(stages[1].status, PlanApprovalStage.Status.WAITING)
        self.assertEqual(submitted.current_approver_id, self.supervisor.id)
        self.assertEqual(submitted.current_stage_id, stages[0].id)
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.PLAN,
                action=AuditEntry.Action.PLAN_SUBMITTED,
                target_id=str(submitted.id),
            ).exists()
        )

    def test_submit_aggregate_balance_exceeded(self):
        # 25 annual working days exceeds the stub's 24-day available balance.
        start = date(2026, 10, 5)
        span = [date(2026, 10, 5) + timedelta(days=i * 7) for i in range(25)]
        blocks = [{"leave_type_id": self.annual_type_id, "start_date": d, "end_date": d} for d in span]
        plan = self.make_plan(blocks=blocks)
        with self.assertRaises(PlanValidationFailedError) as ctx:
            submit_plan(user=self.employee, plan_id=plan.id)
        codes = [e.code for e in ctx.exception.errors]
        self.assertIn("INSUFFICIENT_PLAN_BALANCE", codes)

    def test_submit_rejects_plan_not_owned_and_wrong_state(self):
        plan = self.make_plan()
        other = make_user("other@test.luanar", role=User.Role.EMPLOYEE)
        _profile(other)
        with self.assertRaises(PlanNotFoundError):
            submit_plan(user=other, plan_id=plan.id)
        submitted = submit_plan(user=self.employee, plan_id=plan.id)
        with self.assertRaises(PlanNotSubmittableError):
            submit_plan(user=self.employee, plan_id=submitted.id)


class PeerConflictWarningsTests(PlanServiceBase):
    def setUp(self):
        super().setUp()
        self.peer_a = make_user("peer-a@test.luanar", role=User.Role.EMPLOYEE)
        self.peer_b = make_user("peer-b@test.luanar", role=User.Role.EMPLOYEE)
        self.other_dept = make_user("peer-other@test.luanar", role=User.Role.EMPLOYEE)
        _profile(self.peer_a, department="Science", grade="B")
        _profile(self.peer_b, department="Science", grade="B")
        _profile(self.other_dept, department="Arts", grade="B")
        for peer in (self.peer_a, self.peer_b, self.other_dept):
            self.stub.register_employee(peer)

        self.plan_a = LeaveDayPlan.objects.create(
            employee=self.peer_a,
            period_start=PLAN_START,
            period_end=PLAN_END,
            financial_year_label="2026-27",
            status=LeaveDayPlan.Status.APPROVED,
        )

    def make_published_block(self, user, start, end, status=LeavePlanBlock.Status.CONFIRMED):
        plan = LeaveDayPlan.objects.create(
            employee=user,
            period_start=start,
            period_end=end,
            financial_year_label="2026-27",
            status=LeaveDayPlan.Status.APPROVED,
        )
        return LeavePlanBlock.objects.create(
            plan=plan,
            leave_type_id=self.annual_type_id,
            start_date=start,
            end_date=end,
            working_days=5,
            status=status,
        )

    def make_proposed_plan(self, user, blocks):
        return create_plan(
            user=user,
            period_start=PLAN_START,
            period_end=PLAN_END,
            blocks=blocks,
        )

    def test_overlapping_published_peer_block_is_a_warning(self):
        LeavePlanBlock.objects.create(
            plan=self.plan_a,
            leave_type_id=self.annual_type_id,
            start_date=date(2026, 10, 6),
            end_date=date(2026, 10, 9),
            working_days=4,
            status=LeavePlanBlock.Status.CONFIRMED,
        )
        plan_b = self.make_proposed_plan(
            self.peer_b,
            [{"leave_type_id": self.annual_type_id, "start_date": date(2026, 10, 8), "end_date": date(2026, 10, 12)}],
        )
        warnings = peer_conflicts(plan_b)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["peer_name"], self.peer_a.get_full_name())
        self.assertEqual(warnings[0]["overlaps_start"], "2026-10-08")

    def test_lapsed_peer_block_does_not_conflict(self):
        LeavePlanBlock.objects.create(
            plan=self.plan_a,
            leave_type_id=self.annual_type_id,
            start_date=date(2026, 10, 6),
            end_date=date(2026, 10, 9),
            working_days=4,
            status=LeavePlanBlock.Status.LAPSED,
        )
        plan_b = self.make_proposed_plan(
            self.peer_b,
            [{"leave_type_id": self.annual_type_id, "start_date": BLOCK_START, "end_date": BLOCK_END}],
        )
        self.assertEqual(peer_conflicts(plan_b), [])

    def test_other_department_blocks_do_not_conflict(self):
        self.make_published_block(self.other_dept, date(2026, 10, 6), date(2026, 10, 9))
        plan_b = self.make_proposed_plan(
            self.peer_b,
            [{"leave_type_id": self.annual_type_id, "start_date": date(2026, 10, 8), "end_date": date(2026, 10, 12)}],
        )
        self.assertEqual(peer_conflicts(plan_b), [])


class DecidePlanTests(PlanServiceBase):
    def test_approve_chain_and_final_reservation(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        for approver in (self.supervisor, self.hod, self.registrar, self.dvc):
            stage = plan.current_stage
            plan = decide_plan(
                plan_id=plan.id,
                actor=approver,
                action="approve",
                comment="ok",
                expected_version=stage.decision_version,
            )
        self.assertEqual(plan.status, LeaveDayPlan.Status.APPROVED)
        self.assertEqual(plan.plan_blocks.first().status, LeavePlanBlock.Status.RESERVED)
        reserved = PlanBalanceTransaction.objects.filter(
            block__plan=plan,
            type=PlanBalanceTransaction.Type.RESERVE,
        )
        self.assertEqual(reserved.count(), 1)
        self.assertEqual(reserved.first().days, Decimal("4"))
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.PLAN,
                action=AuditEntry.Action.PLAN_APPROVED,
                target_id=str(plan.id),
            ).exists()
        )

    def test_non_annual_block_reserves_no_balance(self):
        plan = self.make_plan(
            blocks=[{"leave_type_id": self.compassionate_type_id, "start_date": BLOCK_START, "end_date": BLOCK_END}]
        )
        plan = submit_plan(user=self.employee, plan_id=plan.id)
        for approver in (self.supervisor, self.hod, self.registrar, self.dvc):
            stage = plan.current_stage
            plan = decide_plan(
                plan_id=plan.id,
                actor=approver,
                action="approve",
                comment="ok",
                expected_version=stage.decision_version,
            )
        self.assertEqual(
            PlanBalanceTransaction.objects.filter(block__plan=plan).count(),
            0,
        )
        self.assertEqual(plan.plan_blocks.first().status, LeavePlanBlock.Status.RESERVED)

    def test_reject_requires_comment(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        with self.assertRaises(ValueError):
            decide_plan(
                plan_id=plan.id,
                actor=self.supervisor,
                action="reject",
                comment="",
                expected_version=stage.decision_version,
            )

    def test_reject_ends_and_blocks_further_decisions(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        plan = decide_plan(
            plan_id=plan.id,
            actor=self.supervisor,
            action="reject",
            comment="Not this window.",
            expected_version=stage.decision_version,
        )
        self.assertEqual(plan.status, LeaveDayPlan.Status.REJECTED)
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.PLAN,
                action=AuditEntry.Action.PLAN_REJECTED,
            ).exists()
        )

    def test_not_current_approver_rejected(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        from .services import PlanDecisionNotAllowedError

        with self.assertRaises(PlanDecisionNotAllowedError):
            decide_plan(
                plan_id=plan.id,
                actor=self.hod,
                action="approve",
                comment="",
                expected_version=stage.decision_version,
            )

    def test_stale_version_conflict(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        from .services import PlanStageChangedError

        # A previous decision already bumped the version; the caller is stale.
        decide_plan(
            plan_id=plan.id,
            actor=self.supervisor,
            action="approve",
            comment="",
            expected_version=stage.decision_version,
        )
        with self.assertRaises(PlanStageChangedError):
            decide_plan(
                plan_id=plan.id,
                actor=self.supervisor,
                action="approve",
                comment="",
                expected_version=stage.decision_version,
            )


class ConfirmReleaseLapseTests(PlanServiceBase):
    def approve_plan(self, plan):
        plan = submit_plan(user=self.employee, plan_id=plan.id)
        for approver in (self.supervisor, self.hod, self.registrar, self.dvc):
            stage = plan.current_stage
            plan = decide_plan(
                plan_id=plan.id,
                actor=approver,
                action="approve",
                comment="ok",
                expected_version=stage.decision_version,
            )
        return plan

    def test_confirm_locks_block_and_writes_confirm_row(self):
        plan = self.approve_plan(self.make_plan())
        block = plan.plan_blocks.first()
        confirmed = confirm_block(plan.id, block.id, self.employee)
        self.assertEqual(confirmed.status, LeavePlanBlock.Status.CONFIRMED)
        self.assertEqual(
            PlanBalanceTransaction.objects.filter(
                block=block, type=PlanBalanceTransaction.Type.CONFIRM
            ).count(),
            1,
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.PLAN_CONFIRMED,
                target_id=str(plan.id),
            ).exists()
        )

    def test_release_frees_before_start(self):
        plan = self.approve_plan(self.make_plan())
        block = plan.plan_blocks.first()
        released = release_block(plan.id, block.id, self.employee)
        self.assertEqual(released.status, LeavePlanBlock.Status.RELEASED)
        self.assertEqual(
            PlanBalanceTransaction.objects.filter(
                block=block, type=PlanBalanceTransaction.Type.RELEASE
            ).count(),
            1,
        )

    def test_hr_may_release_another_employees_block(self):
        plan = self.approve_plan(self.make_plan())
        hr = make_user("hr@test.luanar", role=User.Role.HR)
        block = plan.plan_blocks.first()
        released = release_block(plan.id, block.id, hr)
        self.assertEqual(released.status, LeavePlanBlock.Status.RELEASED)

    def test_confirm_after_start_rejected(self):
        plan = self.approve_plan(self.make_plan())
        block = plan.plan_blocks.first()
        with mock.patch("plans.services.get_today", return_value=date(2026, 10, 31)):
            with self.assertRaises(BlockStateError):
                confirm_block(plan.id, block.id, self.employee)

    def test_lapse_overdue_blocks_and_notify(self):
        plan = self.approve_plan(self.make_plan())
        block = plan.plan_blocks.first()
        lapse_overdue_blocks(today=date(2026, 11, 2))
        block.refresh_from_db()
        self.assertEqual(block.status, LeavePlanBlock.Status.LAPSED)
        self.assertEqual(
            PlanBalanceTransaction.objects.filter(
                block=block, type=PlanBalanceTransaction.Type.RELEASE
            ).count(),
            1,
        )

    def test_confirmation_reminders_idempotent(self):
        plan = self.approve_plan(self.make_plan())
        from notifications.plans import send_plan_block_confirmation_reminders

        # The window opens 14 days before the block's start (22 Sep); today is
        # pinned past it so a reminder is due, then idempotency holds on rerun.
        with mock.patch(
            "notifications.plans.get_today", return_value=date(2026, 9, 30)
        ):
            first = send_plan_block_confirmation_reminders()
            second = send_plan_block_confirmation_reminders()
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(
            NotificationOutbox.objects.filter(
                kind="plan_block_confirm_reminder"
            ).count(),
            1,
        )


class SupervisorStageTests(TestCase):
    """D20/D21 — the supervisor stage resolves to the assigned supervisor."""

    def test_assigned_supervisor_wins(self):
        employee = make_user("assignee@test.luanar", role=User.Role.EMPLOYEE)
        assigned = make_user("assigned-super@test.luanar", role=User.Role.SUPERVISOR)
        # A lower-id fallback exists, but the assigned supervisor must win.
        fallback = make_user("fallback-super@test.luanar", role=User.Role.SUPERVISOR)
        make_user("chain-hod@test.luanar", role=User.Role.HOD)
        profile = _profile(
            employee, department="Science", grade="B", supervisor=assigned
        )
        self.assertIsNotNone(profile)

        from workflows.models import Workflow, WorkflowStage
        from workflows.providers import DatabaseWorkflowProvider

        Workflow.objects.create(
            name="Science chain",
            department="Science",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        workflow = Workflow.objects.get(name="Science chain")
        WorkflowStage.objects.create(
            workflow=workflow, order=1, approver_role="supervisor"
        )
        WorkflowStage.objects.create(workflow=workflow, order=2, approver_role="hod")

        plan = LeaveDayPlan.objects.create(
            employee=employee,
            period_start=PLAN_START,
            period_end=PLAN_END,
            financial_year_label="2026-27",
            status=LeaveDayPlan.Status.DRAFT,
        )
        LeavePlanBlock.objects.create(
            plan=plan,
            leave_type_id=1,
            start_date=BLOCK_START,
            end_date=BLOCK_END,
            status=LeavePlanBlock.Status.PROPOSED,
        )
        with mock.patch(
            "workflows.providers.get_workflow_provider",
            return_value=DatabaseWorkflowProvider(),
        ):
            from .services import assign_plan_workflow

            active = assign_plan_workflow(plan)
        self.assertEqual(active.role, "supervisor")
        self.assertEqual(active.assigned_approver_id, assigned.id)
        self.assertNotEqual(active.assigned_approver_id, fallback.id)

class PlanAPITests(PlanServiceBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def force(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def create_via_api(self):
        self.force(self.employee)
        return self.client.post(
            "/api/v1/plans/",
            {
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "blocks": [
                    {
                        "leave_type_id": self.annual_type_id,
                        "start_date": "2026-10-06",
                        "end_date": "2026-10-09",
                    }
                ],
            },
            format="json",
        )

    def approve_via_api(self, plan_id):
        for approver in (self.supervisor, self.hod, self.registrar, self.dvc):
            self.force(approver)
            detail = self.client.get(f"/api/v1/plans/approvals/{plan_id}/")
            self.assertEqual(detail.status_code, status.HTTP_200_OK)
            response = self.client.post(
                f"/api/v1/plans/approvals/{plan_id}/decision/",
                {
                    "action": "approve",
                    "comment": "ok",
                    "stage_version": detail.data["decision_version"],
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.force(self.employee)
        plan = LeaveDayPlan.objects.get(pk=plan_id)
        self.assertEqual(plan.status, LeaveDayPlan.Status.APPROVED)
        return plan

    def test_all_endpoints_require_auth(self):
        for method, url in (
            ("get", "/api/v1/plans/"),
            ("post", "/api/v1/plans/"),
            ("get", "/api/v1/plans/approvals/"),
            ("get", "/api/v1/plans/settings/"),
        ):
            response = getattr(self.client, method)(url, data={}, format="json")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_list_and_detail(self):
        create = self.create_via_api()
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        plan_id = create.data["meta"]["id"]
        mine = self.client.get("/api/v1/plans/")
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(mine.data["count"], 1)
        detail = self.client.get(f"/api/v1/plans/{plan_id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["meta"]["status"], "draft")
        self.assertEqual(len(detail.data["blocks"]), 1)

    def test_submit_then_full_approval_web_flow(self):
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        submitted = self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertEqual(submitted.data["meta"]["status"], "submitted")

        plan = self.approve_via_api(plan_id)
        self.assertEqual(
            plan.plan_blocks.first().status, LeavePlanBlock.Status.RESERVED
        )
        block = plan.plan_blocks.first()
        confirmed = self.client.post(
            f"/api/v1/plans/{plan_id}/blocks/{block.id}/confirm/"
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.assertEqual(confirmed.data["status"], "confirmed")

        queue = self.client.get("/api/v1/plans/pending-confirmations/")
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertEqual(queue.data["count"], 0)

    def test_approval_queue_requires_approver_role(self):
        self.force(self.employee)
        response = self.client.get("/api/v1/plans/approvals/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_requires_comment_via_api(self):
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        self.force(self.supervisor)
        detail = self.client.get(f"/api/v1/plans/approvals/{plan_id}/")
        rejected = self.client.post(
            f"/api/v1/plans/approvals/{plan_id}/decision/",
            {
                "action": "reject",
                "comment": "",
                "stage_version": detail.data["decision_version"],
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_peer_conflict_returned_on_submit_response(self):
        peer = make_user("peer-api@test.luanar", role=User.Role.EMPLOYEE)
        _profile(peer, department="Administration", grade="B")
        self.stub.register_employee(peer)
        peer_plan = LeaveDayPlan.objects.create(
            employee=peer,
            period_start=PLAN_START,
            period_end=PLAN_END,
            financial_year_label="2026-27",
            status=LeaveDayPlan.Status.APPROVED,
        )
        LeavePlanBlock.objects.create(
            plan=peer_plan,
            leave_type_id=self.annual_type_id,
            start_date=date(2026, 10, 7),
            end_date=date(2026, 10, 8),
            working_days=2,
            status=LeavePlanBlock.Status.CONFIRMED,
        )
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        submitted = self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertEqual(len(submitted.data["peer_conflicts"]), 1)

    def test_hr_admin_and_settings(self):
        self.force(self.supervisor)
        settings = self.client.get("/api/v1/plans/settings/")
        self.assertEqual(settings.status_code, status.HTTP_403_FORBIDDEN)
        patch = self.client.patch(
            "/api/v1/plans/settings/", {"confirmation_lead_days": 7}
        )
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

        hr = make_user("hr-admin@test.luanar", role=User.Role.HR)
        self.force(hr)
        settings = self.client.get("/api/v1/plans/settings/")
        self.assertEqual(settings.status_code, status.HTTP_200_OK)
        self.assertEqual(settings.data["confirmation_lead_days"], 14)
        patch = self.client.patch(
            "/api/v1/plans/settings/", {"confirmation_lead_days": 7}
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        self.assertEqual(patch.data["confirmation_lead_days"], 7)

        self.create_via_api()
        self.force(hr)
        admin = self.client.get("/api/v1/plans/admin/")
        self.assertEqual(admin.status_code, status.HTTP_200_OK)

    def test_capabilities_counts(self):
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        self.force(self.supervisor)
        capabilities = self.client.get("/api/v1/plans/capabilities/")
        self.assertEqual(capabilities.status_code, status.HTTP_200_OK)
        self.assertTrue(capabilities.data["is_approver"])
        self.assertEqual(capabilities.data["approver_pending_count"], 1)

    def test_team_scoped_list_for_peer(self):
        peer = make_user("peer-team@test.luanar", role=User.Role.EMPLOYEE)
        _profile(peer, department="Administration", grade="B")
        self.stub.register_employee(peer)
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        self.approve_via_api(plan_id)

        self.force(peer)
        team = self.client.get("/api/v1/plans/?scope=team")
        self.assertEqual(team.status_code, status.HTTP_200_OK, team.data)
        self.assertEqual(team.data["count"], 1)
        self.assertEqual(team.data["results"][0]["blocks"][0]["status"], "reserved")
