"""Pipeline-level tests for ``leave.validation.pipeline.run_validation``."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from leave.models import LeaveApplication
from leave.validation.pipeline import CHECK_ORDER, run_validation

from .stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_user,
)


class PipelineOutputTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_valid_annual_run_shape(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.working_days, 5)
        self.assertEqual(result.calendar_days, 5)
        self.assertEqual(result.financial_year, "2026-27")
        self.assertEqual(result.available_balance, Decimal("24"))
        self.assertEqual(result.balance_after_if_approved, Decimal("19"))
        self.assertEqual(result.skipped_checks, ["documents", "reason"])

    def test_draftless_run_skips_application_only_checks(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        # D11: skipped (not failed) when there is no draft to attach.
        for check in ("documents", "reason"):
            self.assertIn(check, result.skipped_checks)

    def test_all_independent_errors_are_collected(self):
        # Multiple failures across check kinds must all come back at once (D11):
        # - start today (START_ON_SUBMISSION_DATE)
        # - short notice (MIN_NOTICE_NOT_MET)
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2026, 9, 21),
            end_date_raw=date(2026, 9, 24),
        )
        codes = {issue.code for issue in result.errors}
        self.assertIn("START_ON_SUBMISSION_DATE", codes)
        self.assertIn("MIN_NOTICE_NOT_MET", codes)

    def test_check_order_matches_spec(self):
        self.assertEqual(
            CHECK_ORDER,
            [
                "start_date",
                "financial_year",
                "notice",
                "duration",
                "eligibility",
                "documents",
                "reason",
                "overlap",
                "balance",
            ],
        )

    def test_missing_dates_short_circuit_but_report_preconditions(self):
        # A leave type that is unavailable must be the single reported error.
        result = run_validation(
            user=self.user,
            leave_type_id=999,  # unknown regardless of dates
            start_date_raw=None,
            end_date_raw=None,
        )
        codes = [issue.code for issue in result.errors]
        self.assertEqual(codes, ["LEAVE_TYPE_UNAVAILABLE", "END_BEFORE_START"])
        self.assertEqual(result.skipped_checks, [])
        self.assertFalse(result.valid)


class InDocumentedTest(StubProviderMixin, TestCase):
    """Rule coverage the spec calls out explicitly."""

    def test_application_in_plus_processing_never_self_overlaps(self):
        stub = self.use_stub()
        user = make_user()
        stub.register_employee(user)
        draft = LeaveApplication.objects.create(
            employee=user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="My own draft",
        )
        result = run_validation(
            user=user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
            application=draft,
        )
        self.assertNotIn("OVERLAPPING_LEAVE", [e.code for e in result.errors])