"""Verification for the Unit 18 seed block (section 3.10).

Runs ``seed_approvals_dev`` against a fresh test database and asserts every
cancellation scenario exists in the required state, eligibility looks right, and
the command is idempotent (no duplicate requests / ledger rows on re-run).
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from leave.cancellations.services import compute_cancellation_eligibility
from leave.models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveApplication,
    LeaveBalanceTransaction,
)
from workflows.management.commands.seed_approvals_dev import (
    FINANCIAL_YEAR_LABEL,
    FIRST_RESERVED_SUFFIX,
    SCENARIOS,
)

CANCEL_SLOT_BASE = len(SCENARIOS)


def _ref(slot: int) -> str:
    return f"LV-{FINANCIAL_YEAR_LABEL}-{FIRST_RESERVED_SUFFIX + slot:06d}"


class SeedCancellationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_approvals_dev", verbosity=0)
        cls.today = timezone.localdate()

        cls.pending_at_stage2 = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 0)
        )
        cls.approved_14d = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 1)
        )
        cls.approved_tomorrow = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 2)
        )
        cls.approved_today = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 3)
        )
        cls.approved_yesterday = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 4)
        )
        cls.approved_maternity = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 5)
        )
        cls.rejected_app = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 6)
        )
        cls.academic_10d = LeaveApplication.objects.get(
            reference_number=_ref(CANCEL_SLOT_BASE + 7)
        )

    def test_pending_application_at_stage_2(self):
        app = self.pending_at_stage2
        self.assertEqual(app.status, LeaveApplication.Status.PENDING)
        self.assertEqual(app.current_stage.role, "dean")
        self.assertEqual(app.current_stage.version, 2)
        self.assertEqual(
            compute_cancellation_eligibility(app)["cancellation_action"], "withdraw"
        )

    def test_approved_14d_carries_5_day_deduction_and_request_action(self):
        app = self.approved_14d
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(app.start_date, self.today + timedelta(days=14))
        deduction = LeaveBalanceTransaction.objects.get(
            application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
        )
        self.assertEqual(deduction.days, Decimal("5"))
        eligibility = compute_cancellation_eligibility(app)
        self.assertEqual(eligibility["cancellation_action"], "request")
        self.assertEqual(eligibility["estimated_restoration_days"], Decimal("5"))
        self.assertEqual(
            eligibility["restoration_financial_year"], FINANCIAL_YEAR_LABEL
        )

    def test_approved_tomorrow_is_cancellable(self):
        app = self.approved_tomorrow
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(app.start_date, self.today + timedelta(days=1))
        self.assertEqual(
            compute_cancellation_eligibility(app)["cancellation_action"], "request"
        )

    def test_approved_today_and_yesterday_are_blocked(self):
        for app, offset in (
            (self.approved_today, 0),
            (self.approved_yesterday, -1),
        ):
            self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
            self.assertEqual(app.start_date, self.today + timedelta(days=offset))
            eligibility = compute_cancellation_eligibility(app)
            self.assertIsNone(eligibility["cancellation_action"])
            self.assertEqual(
                eligibility["cancellation_blocked_reason"], "leave_already_started"
            )

    def test_approved_maternity_has_no_balance_impact(self):
        app = self.approved_maternity
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        eligibility = compute_cancellation_eligibility(app)
        self.assertEqual(eligibility["cancellation_action"], "request")
        self.assertEqual(eligibility["estimated_restoration_days"], Decimal("0"))
        self.assertIsNone(eligibility["restoration_financial_year"])

    def test_rejected_application_is_not_cancellable(self):
        app = self.rejected_app
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(
            compute_cancellation_eligibility(app)["cancellation_blocked_reason"],
            "not_cancellable_status",
        )

    def test_academic_app_has_open_request_at_stage_1_of_2(self):
        app = self.academic_10d
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(app.start_date, self.today + timedelta(days=12))
        self.assertTrue(
            LeaveBalanceTransaction.objects.filter(
                application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
            ).exists()
        )

        request = CancellationRequest.objects.get(application=app)
        self.assertEqual(request.kind, CancellationRequest.Kind.APPROVED_LEAVE)
        self.assertEqual(request.status, CancellationRequest.Status.PENDING)
        self.assertEqual(request.stage_version, 1)
        stages = list(request.stages.all())
        self.assertEqual(
            [stage.role for stage in stages], ["supervisor", "hod"]
        )
        self.assertEqual(
            stages[0].status, CancellationApprovalStage.Status.PENDING
        )
        self.assertEqual(stages[1].status, CancellationApprovalStage.Status.WAITING)
        self.assertEqual(
            compute_cancellation_eligibility(app)["cancellation_blocked_reason"],
            "open_request_exists",
        )

    def test_seed_is_idempotent(self):
        academic = self.academic_10d
        call_command("seed_approvals_dev", verbosity=0)
        self.assertEqual(
            CancellationRequest.objects.filter(application=academic).count(), 1
        )
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(
                application=academic, type=LeaveBalanceTransaction.Type.DEDUCTION
            ).count(),
            1,
        )
        self.assertEqual(
            LeaveApplication.objects.filter(
                reference_number=_ref(CANCEL_SLOT_BASE + 1)
            ).count(),
            1,
        )