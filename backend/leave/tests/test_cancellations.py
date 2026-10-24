"""Unit 18 — leave cancellation tests.

Covers the eligibility matrix, the withdraw vs approval-based request split,
approver decisions and optimistic locking, balance restoration through the
ledger, the employee API, and the approver cancellation API. ``today`` is always
injected as :data:`leave.tests.stubs.TODAY` so the suite never depends on the
wall clock.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.providers.fixture import FixtureRulesProvider
from leave.services.submission import build_rules_snapshot, submit_application
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    TODAY,
    StubProviderMixin,
    ensure_annual_leave_type,
    make_user,
)
from leave.validation.types import ValidationContext
from approvals.models import ApplicationStage, ApplicationStageApprover
from approvals.services import assign_workflow

from leave.cancellations.models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveBalanceTransaction,
)
from leave.cancellations.services import (
    ActionChangedError,
    CommentRequiredError,
    ConfirmationRequiredError,
    DECISION_APPROVE,
    DECISION_REJECT,
    LeaveAlreadyStartedError,
    NoCancellationApproversError,
    NotCancellableError,
    NotCurrentApproverError,
    OpenRequestExistsError,
    ReasonTooLongError,
    ReasonTooShortError,
    RequestNotPendingError,
    SelfDecisionError,
    StaleStageVersionError,
    decide_cancellation,
    get_eligibility,
    submit_cancellation,
)

User = get_user_model()

ANNUAL = {
    "leave_type_id": 1,
    "start_date": EARLIEST_ANNUAL_START,
    "reason": "Family visit",
}

ELIG_URL = "/api/v1/leave-applications/{id}/cancellation-eligibility/"
CANCEL_URL = "/api/v1/leave-applications/{id}/cancel/"
HISTORY_URL = "/api/v1/leave-applications/{id}/cancellations/"
APPROVER_LIST_URL = "/api/v1/approvals/cancellations/"


class CancellationBase(StubProviderMixin, APITestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.employee = make_user(
            "employee@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        self.supervisor = make_user(
            "supervisor@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "hod@luanar", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "registrar@luanar",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        # Directly-built applications have no snapshot, so restoration has to
        # resolve through the current leave rule.
        ensure_annual_leave_type()
        self.stub.register_employee(self.employee)
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
        ):
            self.stub.workflow.register_approver(role, user)

    def make_submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def snapshot_for(self, start, leave_type_id):
        """The ``rules_snapshot`` submission writes for this application.

        The cancellation balance provider reads ``deducts_annual_balance`` from
        the snapshot and refuses to invent a restoration the configuration never
        granted, so an approved row that was built directly rather than
        submitted has to carry a snapshot too — as every real one does. It is
        built with the production builder off the stub's own rules, so it cannot
        drift from what ``submit_application`` writes, and it is built for the
        leave type the row claims: a snapshot disagreeing with its own
        application would be the thing under test.
        """
        return build_rules_snapshot(
            ValidationContext(
                user=self.employee,
                employee=self.stub.employees.get(self.employee.id),
                leave_type=self.stub.get_leave_type_rules(leave_type_id, TODAY),
                start_date=start,
                end_date=start + timedelta(days=3),
                application=None,
                today=TODAY,
                financial_year=self.stub.get_financial_year_for(start),
                holidays={},
                working_days=5,
                calendar_days=7,
                available_balance=Decimal("21"),
            )
        )

    def make_approved(self, start=None, employee=None, leave_type_id=1):
        """An approved annual-leave application with a materialised chain."""
        start = start or (TODAY + timedelta(days=15))
        app = LeaveApplication.objects.create(
            employee=employee or self.employee,
            start_date=start,
            end_date=start + timedelta(days=3),
            working_days=5,
            calendar_days=7,
            financial_year_label="2026-27",
            leave_type_id=leave_type_id,
            reason="Family visit",
            status=LeaveApplication.Status.APPROVED,
            rules_snapshot=self.snapshot_for(start, leave_type_id),
        )
        assign_workflow(app)
        return app

    def closure(self, app):
        """The pending cancellation stage (the current one)."""
        return CancellationApprovalStage.objects.get(
            request__application=app,
            status=CancellationApprovalStage.Status.PENDING,
        )


class EligibilityServiceTests(CancellationBase):
    def test_submitted_can_withdraw(self):
        app = self.make_submitted()
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(eligibility.cancellation_action, "withdraw")
        self.assertIsNone(eligibility.cancellation_blocked_reason)

    def test_approved_future_requests_restoration(self):
        app = self.make_approved()
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(eligibility.cancellation_action, "request")
        self.assertEqual(eligibility.estimated_restoration_days, Decimal("5"))
        self.assertEqual(eligibility.restoration_financial_year, "2026-27")

    def test_approved_started_blocks(self):
        app = self.make_approved(start=TODAY - timedelta(days=1))
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(eligibility.cancellation_blocked_reason, "leave_already_started")
        self.assertIsNone(eligibility.cancellation_action)

    def test_non_approvable_statuses_block(self):
        for status_ in (
            LeaveApplication.Status.DRAFT,
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.CANCELLED,
        ):
            app = self.make_approved()
            app.status = status_
            app.save(update_fields=["status"])
            eligibility = get_eligibility(app, self.employee, today=TODAY)
            self.assertEqual(
                eligibility.cancellation_blocked_reason,
                "not_cancellable_status",
                status_,
            )
            self.assertIsNone(eligibility.cancellation_action)

    def test_open_request_blocks(self):
        app = self.make_approved()
        submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the holiday",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(eligibility.cancellation_blocked_reason, "open_request_exists")

    def test_no_stages_blocks(self):
        app = self.make_approved()
        self.stub.workflow.block_cancellation = True
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(
            eligibility.cancellation_blocked_reason, "no_cancellation_approvers"
        )

    def test_non_deducting_leave_type_returns_zero_restoration(self):
        # Compassionate leave is approved, and the snapshot it was approved
        # under says it never deducted annual leave, so there is nothing to
        # give back. The snapshot travels with the leave type on purpose: an
        # annual-leave snapshot on a compassionate row would be the
        # configuration disagreeing with itself.
        app = self.make_approved(leave_type_id=4)
        eligibility = get_eligibility(app, self.employee, today=TODAY)
        self.assertEqual(eligibility.cancellation_action, "request")
        self.assertEqual(eligibility.estimated_restoration_days, Decimal("0"))
        self.assertIsNone(eligibility.restoration_financial_year)


class WithdrawServiceTests(CancellationBase):
    def test_withdraw_cancels_application_and_stage(self):
        app = self.make_submitted()
        pending_stage = ApplicationStage.objects.get(
            application=app, status=ApplicationStage.Status.PENDING
        )

        cancellation = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="I no longer need this leave",
            confirm=True,
            expected_action="withdraw",
            today=TODAY,
        )

        self.assertEqual(cancellation.kind, CancellationRequest.Kind.WITHDRAWAL)
        self.assertEqual(cancellation.status, CancellationRequest.Status.APPROVED)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        self.assertIsNotNone(app.cancelled_at)
        self.assertIsNone(app.current_stage_id)
        self.assertIsNone(app.current_approver_id)
        pending_stage.refresh_from_db()
        self.assertEqual(pending_stage.status, ApplicationStage.Status.CANCELLED)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CANCELLATION_WITHDRAWN
            ).exists()
        )

    def test_withdraw_requires_confirmation(self):
        app = self.make_submitted()
        with self.assertRaises(ConfirmationRequiredError):
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="I no longer need this leave",
                confirm=False,
                expected_action="withdraw",
                today=TODAY,
            )

    def test_withdraw_validates_reason_length(self):
        app = self.make_submitted()
        with self.assertRaises(ReasonTooShortError):
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="Short",
                confirm=True,
                expected_action="withdraw",
                today=TODAY,
            )
        with self.assertRaises(ReasonTooLongError):
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="x" * 1001,
                confirm=True,
                expected_action="withdraw",
                today=TODAY,
            )

    def test_stale_expected_action_fails_with_fresh_eligibility(self):
        app = self.make_approved()
        with self.assertRaises(ActionChangedError):
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="Changed my mind entirely",
                confirm=True,
                expected_action="withdraw",
                today=TODAY,
            )

    def test_rejected_application_cannot_be_withdrawn(self):
        app = self.make_submitted()
        app.status = LeaveApplication.Status.REJECTED
        app.save(update_fields=["status"])
        with self.assertRaises(NotCancellableError) as ctx:
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="I no longer need this leave",
                confirm=True,
                expected_action=None,
                today=TODAY,
            )
        self.assertEqual(ctx.exception.reason, "not_cancellable_status")


class RequestServiceTests(CancellationBase):
    def test_creates_request_with_stages(self):
        app = self.make_approved()
        cancellation = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        self.assertEqual(cancellation.kind, CancellationRequest.Kind.APPROVED_LEAVE)
        self.assertEqual(cancellation.status, CancellationRequest.Status.PENDING)
        stages = list(cancellation.stages.all())
        self.assertEqual([stage.role for stage in stages], ["supervisor", "hod"])
        self.assertEqual(
            [stage.status for stage in stages],
            [
                CancellationApprovalStage.Status.PENDING,
                CancellationApprovalStage.Status.WAITING,
            ],
        )
        # A cancellation stage is a section: nobody owns it until somebody
        # acts, so the open stage carries its snapshot and a null claimer.
        self.assertIsNone(stages[0].approver_id)
        self.assertIsNone(stages[1].approver_id)
        self.assertEqual(stages[0].eligible_approver_ids(), (self.supervisor.id,))
        self.assertEqual(stages[1].eligible_approver_ids(), (self.hod.id,))
        # The application stays approved until the final approval.
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CANCELLATION_REQUESTED
            ).exists()
        )

    def test_second_request_blocked_while_open(self):
        app = self.make_approved()
        submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        with self.assertRaises(NotCancellableError) as ctx:
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="Now it changed yet again",
                confirm=True,
                expected_action=None,
                today=TODAY,
            )
        self.assertEqual(ctx.exception.reason, "open_request_exists")

    def test_no_approvers_raises_422_semantics(self):
        app = self.make_approved()
        self.stub.workflow.block_cancellation = True
        with self.assertRaises(NoCancellationApproversError):
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="Plans changed for the celebration",
                confirm=True,
                expected_action=None,
                today=TODAY,
            )

    def test_leave_already_started_cannot_be_requested(self):
        app = self.make_approved(start=TODAY - timedelta(days=1))
        with self.assertRaises(NotCancellableError) as ctx:
            submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason="Plans changed for the celebration",
                confirm=True,
                expected_action=None,
                today=TODAY,
            )
        self.assertEqual(ctx.exception.reason, "leave_already_started")


class DecideServiceTests(CancellationBase):
    def _open_request(self, app):
        return CancellationRequest.objects.get(
            application=app, status=CancellationRequest.Status.PENDING
        )

    def test_wrong_approver_forbidden(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        with self.assertRaises(NotCurrentApproverError):
            decide_cancellation(
                user=self.registrar,
                request_id=request.pk,
                decision=DECISION_REJECT,
                comment="Not mine to decide",
                stage_version=1,
                today=TODAY,
            )

    def test_self_decide_forbidden(self):
        # The applicant is excluded from their own sections at materialisation,
        # so this guard is defence in depth against a row that predates it. A
        # colleague on the section is what lets the chain route at all.
        self.stub.register_employee(self.supervisor)
        self.stub.workflow.register_approver(
            "supervisor", make_user("colleague@luanar", role="supervisor")
        )
        app = self.make_approved(employee=self.supervisor)
        ApplicationStageApprover.objects.create(
            stage=app.stages.get(stage_order=1),
            user=self.supervisor,
        )
        request = submit_cancellation(
            user=self.supervisor,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        with self.assertRaises(SelfDecisionError):
            decide_cancellation(
                user=self.supervisor,
                request_id=request.pk,
                decision=DECISION_APPROVE,
                comment="",
                stage_version=1,
                today=TODAY,
            )

    def test_stale_stage_version_rejected(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        with self.assertRaises(StaleStageVersionError):
            decide_cancellation(
                user=self.supervisor,
                request_id=request.pk,
                decision=DECISION_APPROVE,
                comment="",
                stage_version=5,
                today=TODAY,
            )

    def test_reject_requires_comment(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        with self.assertRaises(CommentRequiredError):
            decide_cancellation(
                user=self.supervisor,
                request_id=request.pk,
                decision=DECISION_REJECT,
                comment="",
                stage_version=1,
                today=TODAY,
            )

    def test_reject_ends_request_and_skips_later_stages(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        decided = decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_REJECT,
            comment="Coverage cannot be spared.",
            stage_version=1,
            today=TODAY,
        )
        self.assertEqual(decided.status, CancellationRequest.Status.REJECTED)
        hod_stage = CancellationApprovalStage.objects.get(
            request=request, role="hod"
        )
        self.assertEqual(hod_stage.status, CancellationApprovalStage.Status.NOT_REACHED)
        with self.assertRaises(RequestNotPendingError):
            decide_cancellation(
                user=self.hod,
                request_id=request.pk,
                decision=DECISION_APPROVE,
                comment="",
                stage_version=2,
                today=TODAY,
            )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CANCELLATION_REJECTED
            ).exists()
        )

    def test_approve_moves_to_next_stage_and_increments_version(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        after_supervisor = decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=TODAY,
        )
        self.assertEqual(after_supervisor.stage_version, 2)
        stages = list(after_supervisor.stages.all())
        self.assertEqual(
            [stage.status for stage in stages],
            [
                CancellationApprovalStage.Status.APPROVED,
                CancellationApprovalStage.Status.PENDING,
            ],
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CANCELLATION_STAGE_APPROVED
            ).exists()
        )

    def test_final_approval_cancels_application_and_restores_balance(self):
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=TODAY,
        )
        decided = decide_cancellation(
            user=self.hod,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="Approved.",
            stage_version=2,
            today=TODAY,
        )
        self.assertEqual(decided.status, CancellationRequest.Status.APPROVED)
        self.assertEqual(decided.balance_restored_days, Decimal("5"))
        self.assertEqual(decided.restored_financial_year, "2026-27")
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        self.assertIsNotNone(app.cancelled_at)
        restoration = LeaveBalanceTransaction.objects.get(
            cancellation_request=request,
            type=LeaveBalanceTransaction.Type.RESTORATION,
        )
        self.assertEqual(restoration.days, Decimal("5"))
        self.assertFalse(restoration.carry_forward_eligible)
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(
                cancellation_request=request
            ).count(),
            1,
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CANCELLATION_APPROVED
            ).exists()
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.BALANCE_RESTORED,
                target_type=AuditEntry.TargetType.BALANCE_TRANSACTION,
            ).exists()
        )

    def test_final_approval_after_leave_started_is_refused(self):
        app = self.make_approved(start=TODAY)
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY - timedelta(days=2),
        )
        decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=TODAY - timedelta(days=2),
        )
        with self.assertRaises(LeaveAlreadyStartedError):
            decide_cancellation(
                user=self.hod,
                request_id=request.pk,
                decision=DECISION_APPROVE,
                comment="",
                stage_version=2,
                today=TODAY,
            )
        # The request stays pending so the approver can still reject.
        request.refresh_from_db()
        self.assertEqual(request.status, CancellationRequest.Status.PENDING)
        self.assertEqual(request.stage_version, 2)
        decided = decide_cancellation(
            user=self.hod,
            request_id=request.pk,
            decision=DECISION_REJECT,
            comment="Leave has started.",
            stage_version=2,
            today=TODAY,
        )
        self.assertEqual(decided.status, CancellationRequest.Status.REJECTED)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)

    def test_stale_decision_after_withdrawal_returns_conflict(self):
        app = self.make_submitted()
        withdrawal = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="I no longer need this leave",
            confirm=True,
            expected_action="withdraw",
            today=TODAY,
        )
        self.assertEqual(
            withdrawal.status, CancellationRequest.Status.APPROVED
        )
        # An approver can never decide a withdrawn application.
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)


class LedgerIntegrationTests(CancellationBase):
    def test_available_balance_reflects_restoration(self):
        provider = FixtureRulesProvider()
        provider._grades[self.employee.id] = "B"  # band A-C = 21 days
        self.assertEqual(
            provider.get_available_balance(self.employee.id, "2026-27"),
            Decimal("21"),
        )
        app = self.make_approved()
        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=TODAY,
        )
        decide_cancellation(
            user=self.hod,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=2,
            today=TODAY,
        )
        self.assertEqual(
            provider.get_available_balance(self.employee.id, "2026-27"),
            Decimal("26"),
        )


class EligibilityApiTests(CancellationBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.employee)

    def test_owner_gets_eligibility(self):
        app = self.make_approved()
        response = self.client.get(ELIG_URL.format(id=app.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cancellation_action"], "request")
        self.assertEqual(response.data["estimated_restoration_days"], "5.0")

    def test_other_employee_gets_404(self):
        app = self.make_approved()
        other = make_user("other@luanar")
        self.client.force_authenticate(user=other)
        response = self.client.get(ELIG_URL.format(id=app.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_gets_401(self):
        app = self.make_approved()
        client = self.client.__class__()
        response = client.get(ELIG_URL.format(id=app.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmployeeCancelApiTests(CancellationBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.employee)

    def test_withdraw_returns_200(self):
        app = self.make_submitted()
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "I no longer need this leave",
                "confirm": True,
                "expected_action": "withdraw",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kind"], "withdrawal")
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)

    def test_request_returns_201(self):
        app = self.make_approved()
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "Plans changed for the celebration",
                "confirm": True,
                "expected_action": "request",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["kind"], "approved_leave")
        self.assertEqual(response.data["request"]["status"], "pending")

    def test_missing_confirmation_is_400(self):
        app = self.make_submitted()
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "I no longer need this leave",
                "confirm": False,
                "expected_action": "withdraw",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "confirmation_required")

    def test_stale_expected_action_is_409_with_refreshed_eligibility(self):
        app = self.make_approved()
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "Changed my mind entirely",
                "confirm": True,
                "expected_action": "withdraw",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "action_changed")
        self.assertEqual(
            response.data["eligibility"]["cancellation_action"], "request"
        )

    def test_reason_too_short_is_400(self):
        app = self.make_submitted()
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "Short",
                "confirm": True,
                "expected_action": "withdraw",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "reason_too_short")

    def test_no_approvers_is_422(self):
        app = self.make_approved()
        self.stub.workflow.block_cancellation = True
        response = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "Plans changed for the celebration",
                "confirm": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "no_cancellation_approvers")

    def test_history_lists_requests_newest_first(self):
        app = self.make_approved()
        first = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "First cancellation attempt",
                "confirm": True,
                "expected_action": "request",
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_id = first.data["request"]["id"]

        # The supervisor rejects the first request, closing it.
        self.client.force_authenticate(user=self.supervisor)
        reject = self.client.post(
            f"/api/v1/approvals/cancellations/{first_id}/decision/",
            {"decision": "reject", "comment": "Not now.", "stage_version": 1},
            format="json",
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK)

        # The employee may then submit a fresh request.
        self.client.force_authenticate(user=self.employee)
        second = self.client.post(
            CANCEL_URL.format(id=app.pk),
            {
                "reason": "Second cancellation attempt",
                "confirm": True,
                "expected_action": "request",
            },
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        second_id = second.data["request"]["id"]

        response = self.client.get(HISTORY_URL.format(id=app.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [second_id, first_id])
        kinds = [row["kind"] for row in response.data["results"]]
        self.assertEqual(kinds, ["approved_leave", "approved_leave"])


class ApproverCancellationApiTests(CancellationBase):
    def _open_request(self, app):
        return CancellationRequest.objects.get(
            application=app, status=CancellationRequest.Status.PENDING
        )

    def setUp(self):
        super().setUp()

    def _create_request(self):
        app = self.make_approved()
        submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        return app, self._open_request(app)

    def test_supervisor_sees_pending_but_waiting_hod_does_not(self):
        app, request = self._create_request()

        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(APPROVER_LIST_URL + "?tab=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["request_id"], str(request.id))
        self.assertEqual(row["reference"], app.reference_number)
        self.assertEqual(row["employee_name"], "Ken Employee")
        self.assertEqual(row["current_stage_role"], "supervisor")
        self.assertFalse(row["leave_started"])

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(APPROVER_LIST_URL + "?tab=pending")
        self.assertEqual(response.data["count"], 0)

    def test_detail_and_decision_flow_through_stages(self):
        app, request = self._create_request()

        self.client.force_authenticate(user=self.supervisor)
        detail = self.client.get(
            f"/api/v1/approvals/cancellations/{request.id}/"
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertTrue(detail.data["can_decide"])
        self.assertIsNone(detail.data["my_decision"])
        self.assertEqual(detail.data["stage_version"], 1)

        decision = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "approve", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertEqual(decision.data["stage_version"], 2)
        self.assertFalse(decision.data["can_decide"])

        self.client.force_authenticate(user=self.hod)
        final = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "approve", "comment": "Fine.", "stage_version": 2},
            format="json",
        )
        self.assertEqual(final.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)

        self.client.force_authenticate(user=self.supervisor)
        decided = self.client.get(APPROVER_LIST_URL + "?tab=decided")
        self.assertEqual(decided.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(decided.data["count"], 1)

    def test_stale_version_is_409(self):
        _, request = self._create_request()
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "approve", "comment": "", "stage_version": 9},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "stale_stage_version")

    def test_decided_tab_lists_request_once(self):
        app, request = self._create_request()
        self.client.force_authenticate(user=self.supervisor)
        decision = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "approve", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        decided = self.client.get(APPROVER_LIST_URL + "?tab=decided")
        self.assertEqual(decided.status_code, status.HTTP_200_OK)
        ids = [row["request_id"] for row in decided.data["results"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids.count(str(request.id)), 1)

    def test_reject_requires_comment_400(self):
        _, request = self._create_request()
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "reject", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "comment_required")

    def test_self_decision_returns_403_self_application(self):
        # Defence in depth, as in the service-level case: the applicant is not
        # in the cancellation stage's snapshot, so the guard is only reachable
        # by putting them back. A colleague on the section is what lets the
        # chain route at all.
        self.stub.register_employee(self.supervisor)
        self.stub.workflow.register_approver(
            "supervisor", make_user("colleague@luanar", role="supervisor")
        )
        app = self.make_approved(employee=self.supervisor)
        ApplicationStageApprover.objects.create(
            stage=app.stages.get(stage_order=1),
            user=self.supervisor,
        )
        submit_cancellation(
            user=self.supervisor,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        request = self._open_request(app)
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "approve", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "self_application")

    def test_unassigned_approver_gets_403(self):
        _, request = self._create_request()
        self.client.force_authenticate(user=self.registrar)
        response = self.client.post(
            f"/api/v1/approvals/cancellations/{request.id}/decision/",
            {"decision": "reject", "comment": "Nope.", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "not_current_approver")

    def test_non_approver_gets_403_on_list(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(APPROVER_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_hidden_for_unassigned_approver(self):
        _, request = self._create_request()
        self.client.force_authenticate(user=self.registrar)
        response = self.client.get(
            f"/api/v1/approvals/cancellations/{request.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SharedSectionCancellationTests(CancellationBase):
    """A cancellation stage is a section, so it is any-of too.

    The supervisor section with two members behaves like a leave stage with two
    members: both see the request, either may decide it, and the decision
    records who acted.
    """

    def setUp(self):
        super().setUp()
        self.deputy = make_user(
            "deputy@luanar", role="supervisor", first_name="Dep", last_name="Ut"
        )
        self.stub.workflow.register_approver("supervisor", self.deputy)

    def _open_request(self):
        app = self.make_approved()
        submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed for the celebration",
            confirm=True,
            expected_action="request",
            today=TODAY,
        )
        return CancellationRequest.objects.get(
            application=app, status=CancellationRequest.Status.PENDING
        )

    def test_both_members_hold_the_snapshot(self):
        request = self._open_request()
        stage = request.stages.get(order=1)
        self.assertEqual(
            stage.eligible_approver_ids(),
            tuple(sorted([self.supervisor.id, self.deputy.id])),
        )
        self.assertIsNone(stage.approver_id)

    def test_either_member_may_decide(self):
        request = self._open_request()
        # The deputy, who is not the section's lowest-id member, still decides.
        decided = decide_cancellation(
            user=self.deputy,
            request_id=request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=TODAY,
        )
        stage = decided.stages.get(order=1)
        self.assertEqual(stage.status, CancellationApprovalStage.Status.APPROVED)
        # Acting claims the stage, which is when the approver becomes known.
        self.assertEqual(stage.approver_id, self.deputy.id)

    def test_the_loser_of_a_contested_stage_cannot_decide_afterwards(self):
        request = self._open_request()
        decide_cancellation(
            user=self.supervisor,
            request_id=request.pk,
            decision=DECISION_REJECT,
            comment="Not this time.",
            stage_version=1,
            today=TODAY,
        )
        with self.assertRaises(RequestNotPendingError):
            decide_cancellation(
                user=self.deputy,
                request_id=request.pk,
                decision=DECISION_REJECT,
                comment="Second opinion.",
                stage_version=2,
                today=TODAY,
            )

    def test_a_later_stage_member_cannot_act_early(self):
        request = self._open_request()
        with self.assertRaises(NotCurrentApproverError):
            decide_cancellation(
                user=self.hod,
                request_id=request.pk,
                decision=DECISION_APPROVE,
                comment="",
                stage_version=1,
                today=TODAY,
            )

    def test_both_members_see_the_request_in_the_pending_tab(self):
        request = self._open_request()
        for member in (self.supervisor, self.deputy):
            self.client.force_authenticate(user=member)
            response = self.client.get(APPROVER_LIST_URL)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                [row["request_id"] for row in response.data["results"]],
                [str(request.pk)],
                member.username,
            )

    def test_only_the_actor_sees_it_in_the_decided_tab(self):
        request = self._open_request()
        decide_cancellation(
            user=self.deputy,
            request_id=request.pk,
            decision=DECISION_REJECT,
            comment="Not this time.",
            stage_version=1,
            today=TODAY,
        )
        for member, expected in (
            (self.deputy, 1),
            (self.supervisor, 0),
        ):
            self.client.force_authenticate(user=member)
            response = self.client.get(
                f"{APPROVER_LIST_URL}?tab=decided"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                len(response.data["results"]), expected, member.username
            )

    def test_the_stepper_names_the_snapshot_until_somebody_acts(self):
        request = self._open_request()
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(
            f"/api/v1/approvals/cancellations/{request.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stage = response.data["request"]["stages"][0]
        self.assertIsNone(stage["approver_name"])
        self.assertEqual(len(stage["eligible_approvers"]), 2)
        self.assertTrue(response.data["can_decide"])