"""Unit 25 — leave day plan lifecycle tests.

Leave *rules* come from the stub provider (fixed "today" = 21 Sep 2026), so the
notice period, working-day maths and available balance are deterministic. Plan
*routing* is the real thing: the applicant's team owns a workflow, each of its
active sections becomes a stage, and the stage's eligibility snapshot is every
member of that section minus the applicant. The workflow provider is therefore
patched to :class:`DatabaseWorkflowProvider` while the leave provider stays
stubbed, and the chain is built with the ``workflows.testing`` factories rather
than by hand.

The ``get_today`` clock seam in the plans modules is patched to the same fixed
date so confirm/lapse windows are deterministic.
"""

from datetime import date, timedelta
from dataclasses import replace
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveType
from leave.tests.stubs import TODAY, _leave_types, make_user
from notifications.models import NotificationOutbox
from users.models import EmployeeProfile, User
from workflows.models import Delegation, SectionMember
from workflows.providers import DatabaseWorkflowProvider
from workflows.testing import (
    appoint_approver_to_section,
    build_routing,
    ensure_roles,
    make_approver,
    make_team,
)

from .models import (
    LeaveDayPlan,
    LeavePlanBlock,
    PlanApprovalDecision,
    PlanApprovalStage,
    PlanApprovalStageApprover,
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
    eligible_approver_ids,
    lapse_overdue_blocks,
    peer_conflicts,
    release_block,
    submit_plan,
)

from leave.tests.stubs import StubProviderMixin

User = get_user_model()

CHAIN = ("supervisor", "hod", "registrar", "dvc")

# Plan period: fully inside FY 2026-27, well past the 5-working-day annual
# notice from TODAY (21 Sep 2026).
BLOCK_START = date(2026, 10, 6)
BLOCK_END = date(2026, 10, 9)
PLAN_START = date(2026, 10, 1)
PLAN_END = date(2026, 10, 31)


def _patch_plan_clock(test):
    """Pin ``get_today`` where the plans modules read it, for one test only.

    The patchers are torn down via ``test``'s cleanup chain: a stray pinned
    clock leaks into every later test in the process and makes leave rules look
    unavailable.
    """
    patchers = [
        mock.patch("plans.services.get_today", return_value=TODAY),
        mock.patch("plans.payloads.get_today", return_value=TODAY),
        mock.patch("notifications.plans.get_today", return_value=TODAY),
        mock.patch("plans.views.get_today", return_value=TODAY),
    ]
    for patcher in patchers:
        patcher.start()
        test.addCleanup(patcher.stop)


def _profile(user, **kwargs):
    defaults = dict(
        designation="Officer",
        grade="B",
        appointment_date=date(2022, 3, 15),
        category="administration",
    )
    defaults.update(kwargs)
    return EmployeeProfile.objects.create(user=user, **defaults)


class PlanServiceBase(StubProviderMixin, TestCase):
    """Stubbed leave rules, real team routing.

    The stub provider also swaps in a stub *workflow* provider, which is the
    wrong one here: a plan's chain has to come from the sections HR configured,
    because the whole point of the feature is that it does. So the workflow seam
    is re-patched to the database provider, leaving the leave rules stubbed.
    """

    def setUp(self):
        self.stub = self.use_stub()
        patcher = mock.patch(
            "workflows.providers.get_workflow_provider",
            return_value=DatabaseWorkflowProvider(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        _patch_plan_clock(self)
        self.annual_type_id = self._sync_leave_registry()

        roles = ensure_roles(*CHAIN)
        # Only the registrar is institution-wide; the rest are section members of
        # this one team, so a test can prove who is actually eligible for a stage.
        self.approvers = {
            code: make_approver(
                code,
                username=f"chain-{code}@test.luanar",
                institution_wide=code == "registrar",
                roles=roles,
            )
            for code in CHAIN
        }
        self.supervisor = self.approvers["supervisor"]
        self.hod = self.approvers["hod"]
        self.registrar = self.approvers["registrar"]
        self.dvc = self.approvers["dvc"]

        self.employee = make_user(
            "employee@test.luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        _profile(self.employee)
        self.stub.register_employee(self.employee)
        self.employee, self.team, _ = build_routing(
            employee=self.employee,
            chain=CHAIN,
            approvers=self.approvers,
            institution_wide_roles=("registrar",),
        )
        # ``build_routing`` sets ``profile.team`` on the instance it just loaded,
        # which leaves the user's cached ``employee_profile`` holding a stale
        # ``team_id`` of None even though the row is correct. Re-read the user so
        # scope queries see the team the way the rest of the app does.
        self.employee = User.objects.get(pk=self.employee.pk)
        self.workflow = self.team.workflow

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

    def approve_with(self, plan, actors):
        """Walk the chain, one decision per actor, in section order."""
        for actor in actors:
            stage = plan.current_stage
            plan = decide_plan(
                plan_id=plan.id,
                actor=actor,
                action="approve",
                comment="ok",
                expected_version=stage.decision_version,
            )
        return plan

    def approve_fully(self, plan):
        plan = submit_plan(user=plan.employee, plan_id=plan.id)
        return self.approve_with(
            plan, (self.supervisor, self.hod, self.registrar, self.dvc)
        )


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
        _profile(other, team=self.team)
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

        sections = list(self.workflow.sections.order_by("order"))
        stages = list(submitted.approval_stages.order_by("stage_order"))
        self.assertEqual(len(stages), len(sections))
        self.assertEqual(stages[0].status, PlanApprovalStage.Status.PENDING)
        self.assertTrue(all(s.status == PlanApprovalStage.Status.WAITING for s in stages[1:]))
        self.assertEqual(
            [s.section_ref_id for s in stages], [section.pk for section in sections]
        )
        self.assertEqual(
            [s.role_ref_id for s in stages],
            [section.approver_role_id for section in sections],
        )
        self.assertEqual(submitted.current_stage_id, stages[0].id)
        # The stage is open, so nobody has claimed it yet — that is the whole
        # difference from the old "assigned supervisor" model.
        self.assertIsNone(submitted.current_approver_id)
        self.assertTrue(all(s.assigned_approver_id is None for s in stages))
        self.assertEqual(eligible_approver_ids(submitted), [self.supervisor.id])
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.PLAN,
                action=AuditEntry.Action.PLAN_SUBMITTED,
                target_id=str(submitted.id),
            ).exists()
        )

    def test_the_stage_snapshots_the_single_approver_of_its_section(self):
        """A step holds one approver, snapshotted so a later change cannot move it."""
        section = self.workflow.sections.get(order=1)
        appointee = appoint_approver_to_section(section, "supervisor")
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.approval_stages.get(stage_order=1)

        self.assertEqual(
            set(
                PlanApprovalStageApprover.objects.filter(stage=stage).values_list(
                    "user_id", flat=True
                )
            ),
            {appointee.id},
        )

        # The snapshot is read, not recomputed. Replacing the appointee afterwards
        # must not change who the submitted plan waits for.
        successor = appoint_approver_to_section(
            section,
            "supervisor",
            user=make_approver(
                "supervisor", username="chain-supervisor-2@test.luanar"
            ),
        )
        self.assertEqual(set(eligible_approver_ids(plan, stage)), {appointee.id})
        self.assertNotIn(successor.id, eligible_approver_ids(plan, stage))

    def test_applicant_is_never_in_the_snapshot(self):
        """A member who is also the applicant must not be able to self-approve."""
        for section in self.workflow.sections.all():
            SectionMember.objects.get_or_create(section=section, user=self.employee)
        # The registrar section resolves through its institution-wide holder, so
        # give it a member to make "the employee is a member" the case under test.
        registrar_section = self.workflow.sections.get(order=3)
        SectionMember.objects.get_or_create(section=registrar_section, user=self.registrar)

        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        for stage in plan.approval_stages.all():
            self.assertNotIn(
                self.employee.id,
                PlanApprovalStageApprover.objects.filter(stage=stage).values_list("user_id", flat=True),
            )
        self.assertEqual(eligible_approver_ids(plan), [self.supervisor.id])

        from .services import PlanDecisionNotAllowedError

        with self.assertRaises(PlanDecisionNotAllowedError):
            decide_plan(
                plan_id=plan.id,
                actor=self.employee,
                action="approve",
                comment="",
                expected_version=plan.current_stage.decision_version,
            )

    def test_submit_without_a_team_reports_the_routing_problem(self):
        profile = EmployeeProfile.objects.get(user=self.employee)
        profile.team = None
        profile.save(update_fields=["team"])
        with self.assertRaises(PlanValidationFailedError) as ctx:
            submit_plan(user=self.employee, plan_id=self.make_plan().id)
        self.assertIn("workflow_unavailable", [e.code for e in ctx.exception.errors])

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
        _profile(other, team=self.team)
        with self.assertRaises(PlanNotFoundError):
            submit_plan(user=other, plan_id=plan.id)
        submitted = submit_plan(user=self.employee, plan_id=plan.id)
        with self.assertRaises(PlanNotSubmittableError):
            submit_plan(user=self.employee, plan_id=submitted.id)


class PeerConflictWarningsTests(PlanServiceBase):
    """Peers are the owner's team-mates — the profile look-alike test is gone."""

    def setUp(self):
        super().setUp()
        self.peer_a = make_user("peer-a@test.luanar", role=User.Role.EMPLOYEE)
        self.peer_b = make_user("peer-b@test.luanar", role=User.Role.EMPLOYEE)
        self.peer_c = make_user("peer-c@test.luanar", role=User.Role.EMPLOYEE)
        for peer in (self.peer_a, self.peer_b, self.peer_c):
            _profile(peer, team=self.team)
        for peer in (self.peer_a, self.peer_b, self.peer_c):
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

    def test_another_teams_block_does_not_conflict(self):
        """Same campus, different team: still not a peer."""
        elsewhere = make_user("peer-elsewhere@test.luanar", role=User.Role.EMPLOYEE)
        _profile(elsewhere, team=self.team)
        profile = EmployeeProfile.objects.get(user=elsewhere)
        profile.team = make_team("Second Team", CHAIN, campus="Administration")
        profile.save(update_fields=["team"])
        self.stub.register_employee(elsewhere)

        self.make_published_block(elsewhere, date(2026, 10, 6), date(2026, 10, 9))
        plan_b = self.make_proposed_plan(
            self.peer_b,
            [{"leave_type_id": self.annual_type_id, "start_date": date(2026, 10, 8), "end_date": date(2026, 10, 12)}],
        )
        self.assertEqual(peer_conflicts(plan_b), [])

    def test_employee_without_a_team_has_no_peers(self):
        profile = EmployeeProfile.objects.get(user=self.peer_b)
        profile.team = None
        profile.save(update_fields=["team"])
        plan_b = self.make_proposed_plan(
            self.peer_b,
            [{"leave_type_id": self.annual_type_id, "start_date": date(2026, 10, 8), "end_date": date(2026, 10, 12)}],
        )
        self.assertEqual(peer_conflicts(plan_b), [])


class DecidePlanTests(PlanServiceBase):
    def test_approve_chain_and_final_reservation(self):
        plan = self.approve_fully(self.make_plan())
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

    def test_approver_claiming_a_stage_is_recorded(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        plan = decide_plan(
            plan_id=plan.id,
            actor=self.supervisor,
            action="approve",
            comment="ok",
            expected_version=stage.decision_version,
        )
        stage.refresh_from_db()
        self.assertEqual(stage.assigned_approver_id, self.supervisor.id)
        self.assertEqual(stage.status, PlanApprovalStage.Status.APPROVED)
        self.assertEqual(
            PlanApprovalDecision.objects.get(stage=stage).approver_id, self.supervisor.id
        )
        # The next stage opens, unclaimed.
        self.assertIsNone(plan.current_approver_id)
        self.assertIsNone(plan.current_stage.assigned_approver_id)
        self.assertEqual(plan.current_stage.stage_order, 2)

    def test_appointing_a_second_person_replaces_rather_than_adds(self):
        """A step holds exactly one approver, so a new appointment supersedes.

        This is the rule that removes the race the previous version of this test
        covered: with one approver per step there is no longer a set of eligible
        actors for the first of them to claim and lock the rest out of.
        """
        section = self.workflow.sections.get(order=1)
        superseded = section.approver
        replacement = appoint_approver_to_section(section, "supervisor")

        section.refresh_from_db()
        self.assertEqual(section.approver_id, replacement.pk)
        # The outgoing person's open appointment is closed rather than left open
        # alongside the new one, so "who approves this step" has one answer.
        self.assertFalse(
            SectionMember.objects.filter(
                section=section, user=superseded, effective_to__isnull=True
            ).exists()
        )

    def test_the_superseded_approver_can_no_longer_act(self):
        section = self.workflow.sections.get(order=1)
        superseded = self.supervisor
        appoint_approver_to_section(section, "supervisor")

        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        from .services import PlanDecisionNotAllowedError

        with self.assertRaises(PlanDecisionNotAllowedError):
            decide_plan(
                plan_id=plan.id,
                actor=superseded,
                action="approve",
                comment="",
                expected_version=stage.decision_version,
            )

    def test_eligible_approver_of_a_later_stage_cannot_act_early(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        from .services import PlanDecisionNotAllowedError

        for outsider in (self.hod, self.registrar, self.dvc):
            with self.assertRaises(PlanDecisionNotAllowedError):
                decide_plan(
                    plan_id=plan.id,
                    actor=outsider,
                    action="approve",
                    comment="",
                    expected_version=stage.decision_version,
                )

    def test_delegate_may_act_for_a_section_member(self):
        delegate = make_user("delegate@test.luanar", role=User.Role.APPROVER)
        Delegation.objects.create(
            approver=self.supervisor,
            delegate=delegate,
            starts_on=date(2026, 9, 1),
            ends_on=None,
            requested_by=self.supervisor,
            status=Delegation.Status.APPROVED,
        )
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.current_stage
        plan = decide_plan(
            plan_id=plan.id,
            actor=delegate,
            action="approve",
            comment="ok",
            expected_version=stage.decision_version,
        )
        # The claim records who acted; eligibility stays with the section.
        stage.refresh_from_db()
        self.assertEqual(stage.assigned_approver_id, delegate.id)
        self.assertEqual(
            set(eligible_approver_ids(plan, stage)), {self.supervisor.id}
        )

    def test_non_annual_block_reserves_no_balance(self):
        plan = self.make_plan(
            blocks=[{"leave_type_id": self.compassionate_type_id, "start_date": BLOCK_START, "end_date": BLOCK_END}]
        )
        plan = self.approve_fully(plan)
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


class StageRoutingTests(PlanServiceBase):
    """How the team's workflow becomes this plan's chain."""

    def test_every_active_section_becomes_a_stage(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stages = list(plan.approval_stages.order_by("stage_order"))
        self.assertEqual([s.stage_order for s in stages], [1, 2, 3, 4])
        self.assertEqual(
            [s.role for s in stages], ["supervisor", "hod", "registrar", "dvc"]
        )
        # The role's own history scope is snapshotted beside the role, so the
        # stage still reads correctly after HR edits the role.
        self.assertEqual(
            [s.history_scope for s in stages],
            [
                "all",
                "same_team",
                "current_financial_year",
                "current_financial_year",
            ],
        )
        self.assertTrue(stages[-1].is_final)
        self.assertFalse(any(s.is_final for s in stages[:-1]))

    def test_inactive_section_is_not_a_stage(self):
        self.workflow.sections.filter(order=4).update(is_active=False)
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        self.assertEqual(
            [s.stage_order for s in plan.approval_stages.order_by("stage_order")],
            [1, 2, 3],
        )
        self.assertTrue(plan.approval_stages.get(stage_order=3).is_final)

    def test_a_gap_in_the_section_order_is_refused(self):
        """Same rule as leave: the chain is 1..N, so a mid-chain gap is refused."""
        self.workflow.sections.filter(order=2).update(is_active=False)
        with self.assertRaises(PlanValidationFailedError) as ctx:
            submit_plan(user=self.employee, plan_id=self.make_plan().id)
        self.assertIn("workflow_unavailable", [e.code for e in ctx.exception.errors])

    def test_snapshot_survives_a_later_change_to_the_section(self):
        plan = submit_plan(user=self.employee, plan_id=self.make_plan().id)
        stage = plan.approval_stages.get(stage_order=1)
        SectionMember.objects.filter(section_id=stage.section_ref_id).delete()
        self.assertEqual(eligible_approver_ids(plan, stage), [self.supervisor.id])
        plan = decide_plan(
            plan_id=plan.id,
            actor=self.supervisor,
            action="approve",
            comment="",
            expected_version=stage.decision_version,
        )
        self.assertEqual(plan.status, LeaveDayPlan.Status.SUBMITTED)

    def test_a_draft_team_cannot_route(self):
        self.team.status = self.team.Status.DRAFT
        self.team.save(update_fields=["status"])
        with self.assertRaises(PlanValidationFailedError) as ctx:
            submit_plan(user=self.employee, plan_id=self.make_plan().id)
        self.assertIn("workflow_unavailable", [e.code for e in ctx.exception.errors])

    def test_an_unstaffed_section_is_refused_at_submission(self):
        """A section nobody can act for is refused, not left pending forever."""
        section = self.workflow.sections.get(order=2)
        # A step is staffed through ``Section.approver``; the membership rows are
        # its history. Deleting only the rows leaves a still-staffed step, so the
        # column has to be cleared for this section to be genuinely unstaffed.
        section.approver = None
        section.save(update_fields=["approver"])
        SectionMember.objects.filter(section=section).delete()
        with self.assertRaises(PlanValidationFailedError) as ctx:
            submit_plan(user=self.employee, plan_id=self.make_plan().id)
        self.assertIn("workflow_unavailable", [e.code for e in ctx.exception.errors])


class ConfirmReleaseLapseTests(PlanServiceBase):
    def test_confirm_locks_block_and_writes_confirm_row(self):
        plan = self.approve_fully(self.make_plan())
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
        plan = self.approve_fully(self.make_plan())
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
        plan = self.approve_fully(self.make_plan())
        hr = make_user("hr@test.luanar", role=User.Role.HR)
        block = plan.plan_blocks.first()
        released = release_block(plan.id, block.id, hr)
        self.assertEqual(released.status, LeavePlanBlock.Status.RELEASED)

    def test_confirm_after_start_rejected(self):
        plan = self.approve_fully(self.make_plan())
        block = plan.plan_blocks.first()
        with mock.patch("plans.services.get_today", return_value=date(2026, 10, 31)):
            with self.assertRaises(BlockStateError):
                confirm_block(plan.id, block.id, self.employee)

    def test_lapse_overdue_blocks_and_notify(self):
        plan = self.approve_fully(self.make_plan())
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
        self.approve_fully(self.make_plan())
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

    def test_stage_payload_exposes_the_candidate_set(self):
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        submitted = self.client.post(f"/api/v1/plans/{plan_id}/submit/")
        stages = submitted.data["stages"]
        self.assertEqual(len(stages), 4)
        self.assertEqual(stages[0]["status"], "pending")
        self.assertFalse(stages[0]["is_claimed"])
        self.assertIsNone(stages[0]["assigned_approver_id"])
        self.assertEqual(
            [c["id"] for c in stages[0]["eligible_approvers"]],
            [self.supervisor.id],
        )
        self.assertEqual(stages[0]["eligible_approver_ids"], [self.supervisor.id])
        self.assertIsNotNone(stages[0]["section_ref_id"])
        self.assertIsNotNone(stages[0]["role_ref_id"])
        self.assertEqual(stages[0]["role"], "supervisor")
        self.assertEqual(stages[0]["history_scope"], "all")

    def test_approval_queue_requires_an_approver(self):
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
        _profile(peer, team=self.team)
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

    def test_admin_block_status_filter_returns_each_plan_once(self):
        hr = make_user("hr-admin-blocks@test.luanar", role=User.Role.HR)
        plan = self.make_plan(
            blocks=[
                {
                    "leave_type_id": self.annual_type_id,
                    "start_date": BLOCK_START,
                    "end_date": BLOCK_END,
                },
                {
                    "leave_type_id": self.annual_type_id,
                    "start_date": BLOCK_START + timedelta(days=14),
                    "end_date": BLOCK_END + timedelta(days=14),
                },
            ]
        )
        self.approve_fully(plan)
        self.assertEqual(
            plan.plan_blocks.filter(status=LeavePlanBlock.Status.RESERVED).count(), 2
        )

        self.force(hr)
        admin = self.client.get("/api/v1/plans/admin/?block_status=reserved")
        self.assertEqual(admin.status_code, status.HTTP_200_OK, admin.data)
        ids = [row["id"] for row in admin.data["results"]]
        self.assertEqual(ids.count(str(plan.id)), 1)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(admin.data["count"], len(ids))

    def test_capabilities_counts(self):
        create = self.create_via_api()
        plan_id = create.data["meta"]["id"]
        self.client.post(f"/api/v1/plans/{plan_id}/submit/")

        # A step holds exactly one approver, so the submitted plan is in that one
        # person's queue and nobody else's. The shared-queue case this test used
        # to assert cannot happen any more.
        self.force(self.supervisor)
        capabilities = self.client.get("/api/v1/plans/capabilities/")
        self.assertEqual(capabilities.status_code, status.HTTP_200_OK)
        self.assertTrue(capabilities.data["is_approver"])
        self.assertEqual(capabilities.data["approver_pending_count"], 1)

        # Delegating takes it out of their queue, because the delegate is now the
        # person who has to act.
        # The count is gated on `is_approver`, which is about holding an active
        # approver appointment -- not about system access -- so the delegate
        # needs one or the assertion below would only ever be measuring that.
        delegate = make_approver("supervisor", username="cap-delegate@test.luanar")
        Delegation.objects.create(
            approver=self.supervisor,
            delegate=delegate,
            starts_on=date(2026, 9, 1),
            ends_on=None,
            requested_by=self.supervisor,
            status=Delegation.Status.APPROVED,
        )
        self.force(self.supervisor)
        self.assertEqual(
            self.client.get("/api/v1/plans/capabilities/").data["approver_pending_count"],
            0,
        )
        self.force(delegate)
        self.assertEqual(
            self.client.get("/api/v1/plans/capabilities/").data["approver_pending_count"],
            1,
        )

    def test_team_scoped_list_for_peer(self):
        peer = make_user("peer-team@test.luanar", role=User.Role.EMPLOYEE)
        _profile(peer, team=self.team)
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
        self.assertEqual(team.data["results"][0]["employee_id"], self.employee.id)

    def test_campus_scope_follows_the_teams_campus(self):
        """Campus membership is a property of the team, not the profile."""
        # Campus teams are academic, and an academic team's chain is deliberately
        # simple: the institution-wide registrar only sits on an administration
        # team's chain, so a campus team cannot borrow the base chain.
        admin_team = make_team(
            "Administration Team",
            ("supervisor", "hod"),
            campus="Administration",
            approvers={"supervisor": self.supervisor, "hod": self.hod},
        )
        finance_team = make_team("Finance Team", ("supervisor",), campus="Finance")

        # The base employee moves to the campus team so their campus scope is
        # the Administration campus.
        profile = EmployeeProfile.objects.get(user=self.employee)
        profile.team = admin_team
        profile.save(update_fields=["team"])
        self.employee = User.objects.get(pk=self.employee.pk)

        colleague = make_user("dept-colleague@test.luanar", role=User.Role.EMPLOYEE)
        _profile(colleague, team=admin_team)
        other = make_user("dept-outsider@test.luanar", role=User.Role.EMPLOYEE)
        _profile(other, team=finance_team)
        for user in (colleague, other):
            self.stub.register_employee(user)

        # Finance sees nothing of Administration's plans.
        self.force(other)
        campus = self.client.get("/api/v1/plans/?scope=campus")
        self.assertEqual(campus.status_code, status.HTTP_200_OK, campus.data)
        self.assertEqual(campus.data["count"], 0)

        self.force(colleague)
        self.client.post(
            "/api/v1/plans/",
            {
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "blocks": [
                    {
                        "leave_type_id": self.annual_type_id,
                        "start_date": "2026-10-20",
                        "end_date": "2026-10-21",
                    }
                ],
            },
            format="json",
        )
        plan = LeaveDayPlan.objects.filter(employee=colleague).first()
        plan = submit_plan(user=colleague, plan_id=plan.id)
        self.approve_with(plan, (self.supervisor, self.hod))

        # Colleague's team is at Administration campus, so the outsider's
        # Finance team sees nothing even though both people could share a
        # profile grouping.
        self.force(other)
        campus = self.client.get("/api/v1/plans/?scope=campus")
        self.assertEqual(campus.status_code, status.HTTP_200_OK, campus.data)
        self.assertEqual(campus.data["count"], 0)

        self.force(self.employee)
        campus = self.client.get("/api/v1/plans/?scope=campus")
        self.assertEqual(campus.data["count"], 1)
        self.assertEqual(campus.data["results"][0]["employee_id"], colleague.id)

    def test_all_scope_is_hr_only(self):
        self.force(self.employee)
        self.assertEqual(
            self.client.get("/api/v1/plans/?scope=all").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.force(make_user("hr-scope@test.luanar", role=User.Role.HR))
        self.assertEqual(
            self.client.get("/api/v1/plans/?scope=all").status_code,
            status.HTTP_200_OK,
        )
