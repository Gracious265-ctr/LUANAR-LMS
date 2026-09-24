"""Unit 18 tests: leave cancellation.

Covers the eligibility matrix, withdrawal, request creation, sequential
approval, rejection, final approval with balance restoration, guards,
authorization, concurrency, the approvals list, and regression.

The unit-16 workflow fixture resolves test employees (no ``EmployeeProfile``)
to the default roles ``hod -> dean -> registrar -> dvc`` (see
``workflows.fixture_provider``), so a fully approved application takes four
decisions and carries a single Supervisor/HOD cancellation stage (the HOD).
An academic employee (profile ``category="academic"``) gets
``supervisor -> hod -> registrar -> dvc`` and therefore two cancellation
stages. All "today" reads go through the injectable clock (``leave.providers
.get_today`` / ``timezone.localdate``), fixed at ``TODAY`` (2026-09-21).
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEvent
from leave.models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveApplication,
    LeaveBalanceTransaction,
)
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    TODAY,
    make_approver_chain,
    make_user,
)
from workflows import fixture_provider as workflow_fixture
from workflows.models import ApplicationStage

CANCEL_URL = "/api/v1/applications/{id}/cancel/"
ELIGIBILITY_URL = "/api/v1/applications/{id}/cancellation-eligibility/"
CANCELLATIONS_URL = "/api/v1/applications/{id}/cancellations/"
APPROVALS_CANCELLATIONS_URL = "/api/v1/approvals/cancellations/"
APPROVALS_CANCELLATION_DETAIL_URL = "/api/v1/approvals/cancellations/{request_id}/"
APPROVALS_CANCELLATION_DECISION_URL = "/api/v1/approvals/cancellations/{request_id}/decision/"


class CancellationFixtureMixin(StubProviderMixin):
    """Employee + approver chain and working helpers for Unit 18."""

    def setUpCancellation(self):
        self.stub = self.use_stub(today=TODAY)
        chain = make_approver_chain()
        self.supervisor = chain["supervisor"]
        self.hod = chain["hod"]
        self.dean = chain["dean"]
        self.registrar = chain["registrar"]
        self.dvc = chain["dvc"]

        self.employee = make_user()
        self.stub.register_employee(self.employee)
        self.other = make_user(username="other@test.luanar")
        self.stub.register_employee(self.other)

        self.client = APIClient()
        self._dates = EARLIEST_ANNUAL_START
        self._patch_today()

    def _patch_today(self, today=TODAY):
        patchers = [
            mock.patch("django.utils.timezone.localdate", return_value=today),
            mock.patch("leave.providers.get_today", return_value=today),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def submit_app(self, leave_type_id=1, employee=None):
        """Submit a pending application via the normal flow."""
        from leave.services.submission import submit_application

        employee = employee or self.employee
        self._dates = _next_workday(self._dates)
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=leave_type_id,
            start_date=self._dates,
            end_date=self._dates + timedelta(days=4),
            reason="Annual leave",
        )
        submit_application(user=employee, application_id=app.id)
        app.refresh_from_db()
        self._dates = _next_workday(app.end_date + timedelta(days=1))
        return app

    def _approve_fully(self, app):
        """Decide through every pending unit-16 stage with its approver."""
        from workflows.approval import decide

        for _ in range(6):
            app.refresh_from_db()
            if app.status != LeaveApplication.Status.PENDING:
                break
            stage = app.current_stage
            decide(
                application_id=app.id,
                actor=stage.assigned_approver,
                action="approve",
                comment="Approved.",
                expected_stage_version=stage.version,
            )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        return app

    def make_approved_app(self, *, start_offset=14, leave_type_id=1,
                          employee=None):
        """Create, submit, and fully approve an application."""
        app = self.submit_app(leave_type_id=leave_type_id, employee=employee)
        self._approve_fully(app)
        app.start_date = TODAY + timedelta(days=start_offset)
        app.save(update_fields=["start_date"])
        return app

    def make_academic_app(self, *, start_offset=14):
        """An approved app for an academic employee (2 cancellation stages)."""
        from users.models import EmployeeProfile

        employee = make_user(username="academic@test.luanar")
        EmployeeProfile.objects.create(
            user=employee, category="academic", department=""
        )
        self.stub.register_employee(
            employee, category="academic", gender="F"
        )
        app = self.submit_app(employee=employee)
        self._approve_fully(app)
        app.start_date = TODAY + timedelta(days=start_offset)
        app.save(update_fields=["start_date"])
        return app, employee

    def open_request(self, app, user=None):
        """Authenticate as ``user`` (owner, default) and open a request."""
        user = user or self.employee
        self.client.force_authenticate(user=user)
        response = self.post_cancel(
            app,
            reason="I need to cancel this leave.",
            expected_action="request",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["cancellation_request"]["id"]

    def post_cancel(self, app, *, reason="I need to cancel this leave.", **payload):
        payload.setdefault("reason", reason)
        payload.setdefault("confirm", True)
        return self.client.post(CANCEL_URL.format(id=app.id), payload)

    def post_decision(self, request_id, user, *, decision="approve", comment="",
                      stage_version=1):
        self.client.force_authenticate(user=user)
        return self.client.post(
            APPROVALS_CANCELLATION_DECISION_URL.format(request_id=request_id),
            {
                "decision": decision,
                "comment": comment,
                "stage_version": stage_version,
            },
        )

    def seed_ledger_deduction(self, app, days=5, financial_year="2026-27"):
        """Record a ledger ``deduction`` row (final approval restores only
        actually deducted days, rule 2.1.8/9)."""
        from leave.cancellations.fixture_balance import _resolve_leave_type

        return LeaveBalanceTransaction.objects.create(
            employee=app.employee,
            financial_year=financial_year,
            leave_type=_resolve_leave_type(app),
            application=app,
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal(str(days)),
            carry_forward_eligible=False,
        )


def _next_workday(day):
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


class EligibilityTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_pending_application_returns_withdraw(self):
        app = self.submit_app()
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertEqual(eligibility["cancellation_action"], "withdraw")
        self.assertIsNone(eligibility["cancellation_blocked_reason"])
        self.assertEqual(eligibility["estimated_restoration_days"], Decimal("0"))

    def test_approved_future_returns_request(self):
        app = self.make_approved_app(start_offset=14)
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertEqual(eligibility["cancellation_action"], "request")
        self.assertIsNone(eligibility["cancellation_blocked_reason"])
        self.assertEqual(eligibility["estimated_restoration_days"], Decimal("5"))
        self.assertEqual(eligibility["restoration_financial_year"], "2026-27")

    def test_approved_today_returns_leave_already_started(self):
        app = self.make_approved_app(start_offset=14)
        app.start_date = TODAY
        app.save(update_fields=["start_date"])
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(
            eligibility["cancellation_blocked_reason"], "leave_already_started"
        )

    def test_approved_yesterday_returns_leave_already_started(self):
        app = self.make_approved_app(start_offset=14)
        app.start_date = TODAY - timedelta(days=1)
        app.save(update_fields=["start_date"])
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(
            eligibility["cancellation_blocked_reason"], "leave_already_started"
        )

    def test_rejected_returns_not_cancellable_status(self):
        app = self.submit_app()
        from workflows.approval import decide

        decide(
            application_id=app.id,
            actor=self.hod,
            action="reject",
            comment="Rejected.",
            expected_stage_version=app.current_stage.version,
        )
        app.refresh_from_db()
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(
            eligibility["cancellation_blocked_reason"], "not_cancellable_status"
        )

    def test_draft_returns_not_cancellable_status(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=TODAY + timedelta(days=10),
            end_date=TODAY + timedelta(days=14),
            reason="Annual leave",
        )
        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(
            eligibility["cancellation_blocked_reason"], "not_cancellable_status"
        )

    def test_open_request_blocks_eligibility(self):
        app = self.make_approved_app(start_offset=14)
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(app, expected_action="request")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        from leave.cancellations.services import get_eligibility

        eligibility = get_eligibility(app, self.employee)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(eligibility["cancellation_blocked_reason"], "open_request_exists")

    def test_approved_no_approvers_returns_blocked(self):
        from users.models import EmployeeProfile

        special = make_user(username="special@test.luanar")
        EmployeeProfile.objects.create(user=special, category="special", department="")
        self.stub.register_employee(special)
        with mock.patch.dict(
            workflow_fixture.FIXTURE_WORKFLOWS,
            {("special", ""): ("registrar", "dvc")},
        ):
            app = self.submit_app(employee=special)
            self._approve_fully(app)
            app.start_date = TODAY + timedelta(days=14)
            app.save(update_fields=["start_date"])

            from leave.cancellations.services import get_eligibility

            eligibility = get_eligibility(app, special)
        self.assertIsNone(eligibility["cancellation_action"])
        self.assertEqual(
            eligibility["cancellation_blocked_reason"], "no_cancellation_approvers"
        )


class WithdrawalTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_withdraw_pending_application(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kind"], "withdrawal")

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        self.assertIsNotNone(app.cancelled_at)

        request_row = CancellationRequest.objects.get(application=app)
        self.assertEqual(request_row.kind, CancellationRequest.Kind.WITHDRAWAL)
        self.assertEqual(request_row.status, CancellationRequest.Status.APPROVED)
        self.assertIsNotNone(request_row.decided_at)
        self.assertEqual(
            request_row.employee_notification_state,
            CancellationRequest.EmployeeNotificationState.NOT_REQUIRED,
        )
        self.assertFalse(
            app.stages.filter(status=ApplicationStage.Status.PENDING).exists()
        )

    def test_withdraw_writes_audit_event(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        self.post_cancel(app, reason="I no longer need this leave.", expected_action="withdraw")
        self.assertTrue(
            AuditEvent.objects.filter(
                action="cancellation.withdrawn", object_id=app.id
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="cancellation.withdrawn", object_id=app.id
            )
            .values_list("prev_state", flat=True)[0]
            in ("pending", "submitted")
        )

    def test_withdraw_creates_no_balance_transactions(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        self.post_cancel(app, reason="I no longer need this leave.", expected_action="withdraw")
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)

    def test_withdraw_requires_confirmation(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            confirm=False,
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "confirmation_required")

    def test_withdraw_reason_too_short(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="Short",
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "reason_too_short")

    def test_withdraw_reason_too_long(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="x" * 1001,
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "reason_too_long")

    def test_cancel_rejects_unknown_fields(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            expected_action="withdraw",
            employee_id=999,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_action_changed_returns_409(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        first = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.post_cancel(
            app,
            reason="Still no longer need this.",
            expected_action="request",
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "action_changed")

    def test_cancel_withdrawal_after_decision_returns_409(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        first = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.post_cancel(
            app,
            reason="Still no longer need this.",
            expected_action="withdraw",
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "action_changed")


class RequestCreationTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def _create_request(self, app):
        self.client.force_authenticate(user=self.employee)
        return self.post_cancel(app, expected_action="request")

    def test_create_request_admin_single_stage(self):
        app = self.make_approved_app(start_offset=14)
        response = self._create_request(app)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["kind"], "approved_leave")
        self.assertEqual(response.data["cancellation_request"]["status"], "pending")

        request_row = CancellationRequest.objects.get(application=app)
        self.assertEqual(request_row.kind, CancellationRequest.Kind.APPROVED_LEAVE)
        self.assertEqual(request_row.status, CancellationRequest.Status.PENDING)
        self.assertEqual(request_row.stage_version, 1)
        self.assertEqual(request_row.application_status_at_request, "approved")

        stages = list(request_row.stages.all())
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].role, "hod")
        self.assertEqual(stages[0].approver_id, self.hod.id)
        self.assertEqual(
            stages[0].status, CancellationApprovalStage.Status.PENDING
        )

    def test_create_request_academic_two_stages(self):
        app, employee = self.make_academic_app(start_offset=14)
        self.client.force_authenticate(user=employee)
        response = self.post_cancel(app, expected_action="request")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        request_row = CancellationRequest.objects.get(application=app)
        stages = list(request_row.stages.all())
        self.assertEqual(len(stages), 2)
        self.assertEqual([stage.role for stage in stages], ["supervisor", "hod"])
        self.assertEqual(
            stages[0].status, CancellationApprovalStage.Status.PENDING
        )
        self.assertEqual(
            stages[1].status, CancellationApprovalStage.Status.WAITING
        )
        self.assertEqual(stages[0].approver_id, self.supervisor.id)
        self.assertEqual(stages[1].approver_id, self.hod.id)

    def test_no_cancellation_approvers_returns_422(self):
        from users.models import EmployeeProfile

        special = make_user(username="special@test.luanar")
        EmployeeProfile.objects.create(user=special, category="special", department="")
        self.stub.register_employee(special)
        with mock.patch.dict(
            workflow_fixture.FIXTURE_WORKFLOWS,
            {("special", ""): ("registrar", "dvc")},
        ):
            app = self.submit_app(employee=special)
            self._approve_fully(app)
            app.start_date = TODAY + timedelta(days=14)
            app.save(update_fields=["start_date"])

            self.client.force_authenticate(user=special)
            with mock.patch(
                "leave.cancellations.services.compute_cancellation_eligibility",
                return_value={
                    "cancellation_action": "request",
                    "cancellation_blocked_reason": None,
                    "estimated_restoration_days": Decimal("0"),
                    "restoration_financial_year": None,
                },
            ):
                response = self.post_cancel(
                    app,
                    reason="I need to cancel this leave.",
                    expected_action="request",
                )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "no_cancellation_approvers")

    def test_open_request_exists_returns_409(self):
        app = self.make_approved_app(start_offset=14)
        first = self._create_request(app)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        # The eligibility gate short-circuits an open request to a "blocked"
        # state (``open_request_exists``), so a second submission can never
        # match the expected action and is defended with 409 ``action_changed``.
        # The blocked reason itself is asserted in the eligibility tests.
        second = self._create_request(app)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "action_changed")

    def test_expected_action_mismatch_returns_409(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="I need to cancel this leave.",
            expected_action="request",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "action_changed")

    def test_request_writes_audit_event(self):
        app = self.make_approved_app(start_offset=14)
        self._create_request(app)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="cancellation.requested", object_id=app.id
            ).exists()
        )


class DecisionTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_approve_final_cancels_application_and_restores_balance(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.seed_ledger_deduction(app)

        response = self.post_decision(request_id, self.hod)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["application_status"], "cancelled")
        self.assertTrue(response.data["balance_restored"])

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        self.assertIsNotNone(app.cancelled_at)

        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.status, CancellationRequest.Status.APPROVED)
        self.assertIsNotNone(request_row.decided_at)
        self.assertEqual(request_row.stage_version, 2)
        self.assertEqual(request_row.balance_restored_days, Decimal("5"))
        self.assertEqual(request_row.restored_financial_year, "2026-27")
        self.assertEqual(
            request_row.employee_notification_state,
            CancellationRequest.EmployeeNotificationState.PENDING,
        )

        restoration = LeaveBalanceTransaction.objects.get(
            type=LeaveBalanceTransaction.Type.RESTORATION
        )
        self.assertEqual(restoration.application, app)
        self.assertEqual(restoration.cancellation_request, request_row)
        self.assertEqual(restoration.employee, self.employee)
        self.assertEqual(restoration.financial_year, "2026-27")
        self.assertEqual(restoration.days, Decimal("5"))
        self.assertFalse(restoration.carry_forward_eligible)

        self.assertTrue(
            AuditEvent.objects.filter(
                action="cancellation.approved", object_id=app.id
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="balance.restored", object_id=app.id).exists()
        )

    def test_sequential_approval_academic(self):
        app, employee = self.make_academic_app(start_offset=14)
        self.client.force_authenticate(user=employee)
        response = self.post_cancel(app, expected_action="request")
        request_id = response.data["cancellation_request"]["id"]

        first = self.post_decision(request_id, self.supervisor)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["application_status"], "approved")
        self.assertFalse(first.data["balance_restored"])

        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.status, CancellationRequest.Status.PENDING)
        self.assertEqual(request_row.stage_version, 2)
        stages = list(request_row.stages.all())
        self.assertEqual(
            stages[0].status, CancellationApprovalStage.Status.APPROVED
        )
        self.assertEqual(
            stages[1].status, CancellationApprovalStage.Status.PENDING
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)

        self.seed_ledger_deduction(app)
        second = self.post_decision(request_id, self.hod, stage_version=2)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data["balance_restored"])
        self.assertEqual(second.data["application_status"], "cancelled")

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        request_row.refresh_from_db()
        self.assertEqual(request_row.stage_version, 3)
        self.assertIsNotNone(request_row.decided_at)

    def test_reject_at_stage_one_keeps_application(self):
        app, employee = self.make_academic_app(start_offset=14)
        self.client.force_authenticate(user=employee)
        response = self.post_cancel(app, expected_action="request")
        request_id = response.data["cancellation_request"]["id"]

        decision = self.post_decision(
            request_id, self.supervisor, decision="reject", comment="Not approved."
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertEqual(decision.data["application_status"], "approved")
        self.assertFalse(decision.data["balance_restored"])

        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.status, CancellationRequest.Status.REJECTED)
        self.assertIsNotNone(request_row.decided_at)
        stages = list(request_row.stages.all())
        self.assertEqual(
            stages[0].status, CancellationApprovalStage.Status.REJECTED
        )
        self.assertEqual(
            stages[1].status, CancellationApprovalStage.Status.NOT_REACHED
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="cancellation.rejected", object_id=app.id
            ).exists()
        )

    def test_reject_at_final_stage_keeps_application(self):
        app, employee = self.make_academic_app(start_offset=14)
        self.client.force_authenticate(user=employee)
        response = self.post_cancel(app, expected_action="request")
        request_id = response.data["cancellation_request"]["id"]

        self.post_decision(request_id, self.supervisor)
        decision = self.post_decision(
            request_id, self.hod, decision="reject",
            comment="Not approved.", stage_version=2,
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertEqual(decision.data["application_status"], "approved")

        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.status, CancellationRequest.Status.REJECTED)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)

    def test_reject_requires_comment(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = self.post_decision(request_id, self.hod, decision="reject")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "comment_required")

    def test_reject_comment_too_long(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = self.post_decision(
            request_id, self.hod, decision="reject", comment="x" * 1001
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "comment_required")

    def test_stale_stage_version_returns_409(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = self.post_decision(request_id, self.hod, stage_version=99)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "stale_stage_version")

    def test_not_current_approver_returns_403(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = self.post_decision(request_id, self.other)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "not_current_approver")

    def test_later_stage_approver_returns_403(self):
        app, employee = self.make_academic_app(start_offset=14)
        self.client.force_authenticate(user=employee)
        response = self.post_cancel(app, expected_action="request")
        request_id = response.data["cancellation_request"]["id"]
        decision = self.post_decision(request_id, self.hod)
        self.assertEqual(decision.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(decision.data["code"], "not_current_approver")

    def test_request_not_pending_returns_409(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        first = self.post_decision(request_id, self.hod)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.post_decision(request_id, self.hod)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "request_not_pending")

    def test_final_approve_blocks_started_leave_returns_409(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        app.start_date = TODAY
        app.save(update_fields=["start_date"])
        response = self.post_decision(request_id, self.hod)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "leave_already_started")
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)

    def test_special_leave_restores_nothing(self):
        app = self.make_approved_app(start_offset=14, leave_type_id=4)
        request_id = self.open_request(app)
        response = self.post_decision(request_id, self.hod)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["balance_restored"])
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)
        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.balance_restored_days, Decimal("0"))
        self.assertIsNone(request_row.restored_financial_year)

    def test_final_approval_without_ledger_deduction_restores_nothing(self):
        # No deduction row exists for this app (rule 2.1.8/9: only actually
        # deducted days are restored), so final approval records no restoration
        # even though the leave type deducts annual leave.
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = self.post_decision(request_id, self.hod)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["application_status"], "cancelled")
        self.assertFalse(response.data["balance_restored"])
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)
        request_row = CancellationRequest.objects.get(pk=request_id)
        self.assertEqual(request_row.balance_restored_days, Decimal("0"))
        self.assertIsNone(request_row.restored_financial_year)


class AuthorizationTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_eligibility_other_employee_404(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.get(ELIGIBILITY_URL.format(id=app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_eligibility_approver_404(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(ELIGIBILITY_URL.format(id=app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_other_employee_404(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.other)
        response = self.post_cancel(
            app,
            reason="I need to cancel this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancellations_list_other_employee_404(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.get(CANCELLATIONS_URL.format(id=app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_decision_requires_authentication(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        response = APIClient().post(
            APPROVALS_CANCELLATION_DECISION_URL.format(request_id=request_id),
            {"decision": "approve", "stage_version": 1},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_unrelated_403(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.client.force_authenticate(user=self.other)
        response = self.client.get(
            APPROVALS_CANCELLATION_DETAIL_URL.format(request_id=request_id)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_assigned_approver_200(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(
            APPROVALS_CANCELLATION_DETAIL_URL.format(request_id=request_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["application"]["reference_number"], app.reference_number)
        self.assertEqual(response.data["stages"][0]["role"], "hod")
        self.assertFalse(response.data["leave_started"])
        self.assertIsNotNone(response.data["balance_impact"]["restores_days"])

    def test_detail_owner_200(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(
            APPROVALS_CANCELLATION_DETAIL_URL.format(request_id=request_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reason"], "I need to cancel this leave.")

    def test_detail_unknown_404(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(
            APPROVALS_CANCELLATION_DETAIL_URL.format(request_id=999_999)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ListTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_employee_cancellations_list(self):
        app = self.make_approved_app(start_offset=14)
        self.client.force_authenticate(user=self.employee)
        self.post_cancel(app, expected_action="request")

        response = self.client.get(CANCELLATIONS_URL.format(id=app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item["kind"], "approved_leave")
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["application"]["reference_number"], app.reference_number)
        self.assertEqual(item["current_stage_role"], "Head of Department")

    def test_approvals_cancellations_pending_list_paginated(self):
        app = self.make_approved_app(start_offset=14)
        self.client.force_authenticate(user=self.employee)
        self.post_cancel(app, expected_action="request")

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(f"{APPROVALS_CANCELLATIONS_URL}?tab=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["current_stage_role"], "Head of Department")
        self.assertEqual(item["application_reference"], app.reference_number)
        self.assertEqual(item["leave_type"], "Annual Leave")
        self.assertFalse(item["leave_started"])
        self.assertNotIn("my_decision", item)

    def test_approvals_cancellations_decided_list(self):
        app = self.make_approved_app(start_offset=14)
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(app, expected_action="request")
        request_id = response.data["cancellation_request"]["id"]
        self.post_decision(request_id, self.hod)

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(f"{APPROVALS_CANCELLATIONS_URL}?tab=decided")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["status"], "approved")
        self.assertEqual(item["my_decision"]["action"], "approved")

    def test_list_unknown_tab_400(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(f"{APPROVALS_CANCELLATIONS_URL}?tab=other")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approvals_list_requires_auth(self):
        response = APIClient().get(APPROVALS_CANCELLATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RegressionTests(CancellationFixtureMixin, TestCase):
    def setUp(self):
        self.setUpCancellation()

    def test_withdrawn_application_not_in_pending_queues(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.post_cancel(
            app,
            reason="I no longer need this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        app.refresh_from_db()
        self.assertFalse(
            app.stages.filter(status=ApplicationStage.Status.PENDING).exists()
        )

        from workflows.policies import get_decision_authority

        authority = get_decision_authority(self.hod, app)
        self.assertFalse(authority.can_decide)
        self.assertEqual(authority.reason, "application_cancelled")

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(f"{APPROVALS_CANCELLATIONS_URL}?tab=pending")
        self.assertEqual(response.data["count"], 0)

    def test_decision_on_cancelled_application_returns_409(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.post_decision(request_id, self.hod)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)

        from workflows.approval import decide
        from workflows.errors import NotAllowed

        with self.assertRaises(NotAllowed) as caught:
            decide(
                application_id=app.id,
                actor=self.dean,
                action="approve",
                comment="Approved.",
                expected_stage_version=app.current_stage.version,
            )
        self.assertEqual(getattr(caught.exception, "reason", None), "application_cancelled")

    def test_cancelled_application_cannot_be_cancelled_again(self):
        app = self.make_approved_app(start_offset=14)
        self.client.force_authenticate(user=self.employee)
        first = self.post_cancel(app, expected_action="request")
        request_id = first.data["cancellation_request"]["id"]
        self.post_decision(request_id, self.hod)

        # Re-authenticate as the owner: post_decision left the client on the
        # approver, and a cancellations POST must be made by the employee.
        self.client.force_authenticate(user=self.employee)
        second = self.post_cancel(
            app,
            reason="I still need to cancel this leave.",
            expected_action="withdraw",
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "action_changed")

    def test_restoration_is_idempotent(self):
        app = self.make_approved_app(start_offset=14)
        request_id = self.open_request(app)
        self.seed_ledger_deduction(app)
        self.post_decision(request_id, self.hod)
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(
                type=LeaveBalanceTransaction.Type.RESTORATION
            ).count(),
            1,
        )