"""Validator behavior tests, driven through ``run_validation`` with a stub provider.

Each test fixes the reference date (Monday 21 Sep 2026) and asserts on the
specific error codes + messages/fields defined by Unit 14.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from leave.models import LeaveApplication
from leave.validation.pipeline import run_validation

from .stubs import (
    EARLIEST_ANNUAL_START,
    HOLIDAY,
    TODAY,
    StubProviderMixin,
    make_user,
)

VALID_RANGE = (EARLIEST_ANNUAL_START, date(2026, 10, 2))  # Mon 28 Sep - Fri 2 Oct


class StartDateValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def run_check(self, start, end, leave_type_id=1, application=None):
        return run_validation(
            user=self.user,
            leave_type_id=leave_type_id,
            start_date_raw=start,
            end_date_raw=end,
            application=application,
        )

    def test_start_today_fails(self):
        result = self.run_check(TODAY, date(2026, 10, 2))
        self.assertIn(
            "START_ON_SUBMISSION_DATE", [e.code for e in result.errors]
        )

    def test_start_in_past_fails(self):
        result = self.run_check(date(2026, 9, 14), date(2026, 9, 18))
        codes = [e.code for e in result.errors]
        self.assertIn("START_IN_PAST", codes)
        self.assertIn("MIN_NOTICE_NOT_MET", codes)  # D11: all errors returned

    def test_start_on_weekend_fails(self):
        result = self.run_check(date(2026, 9, 26), date(2026, 9, 29))
        codes = [e.code for e in result.errors]
        self.assertIn("START_NOT_WORKING_DAY", codes)
        self.assertIn("MIN_NOTICE_NOT_MET", codes)

    def test_start_on_holiday_fails(self):
        self.stub.add_holiday(HOLIDAY)
        result = self.run_check(HOLIDAY, date(2026, 10, 2))
        issue = next(e for e in result.errors if e.code == "START_NOT_WORKING_DAY")
        self.assertEqual(issue.field, "start_date")
        self.assertIn("public holiday", issue.message)


class NoticeValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_short_notice_fails_with_earliest_start(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2026, 9, 22),
            end_date_raw=date(2026, 9, 25),
        )
        issue = next(e for e in result.errors if e.code == "MIN_NOTICE_NOT_MET")
        self.assertEqual(issue.field, "start_date")
        self.assertEqual(issue.detail["required"], 5)
        self.assertEqual(issue.detail["unit"], "working_days")
        self.assertEqual(
            issue.detail["earliest_start"], EARLIEST_ANNUAL_START.isoformat()
        )

    def test_exact_notice_passes(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertNotIn("MIN_NOTICE_NOT_MET", [e.code for e in result.errors])
        self.assertTrue(result.valid)


class DurationValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_compassionate_over_max_working_days_fails(self):
        start, end = EARLIEST_ANNUAL_START, date(2026, 10, 5)  # 6 working days
        result = run_validation(
            user=self.user,
            leave_type_id=4,  # compassionate, max 5 working days
            start_date_raw=start,
            end_date_raw=end,
        )
        issue = next(e for e in result.errors if e.code == "MAX_DURATION_EXCEEDED")
        self.assertEqual(issue.field, "end_date")
        self.assertEqual(issue.detail["max_duration"], 5)
        self.assertEqual(issue.detail["measured"], 6)

    def test_at_max_passes(self):
        result = run_validation(
            user=self.user,
            leave_type_id=4,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertNotIn("MAX_DURATION_EXCEEDED", [e.code for e in result.errors])


class FinancialYearValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_start_outside_all_years_fails(self):
        start = date(2028, 7, 1)  # after every configured fiscal year
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=start,
            end_date_raw=date(2028, 7, 2),
        )
        codes = [e.code for e in result.errors]
        self.assertIn("NO_FINANCIAL_YEAR_CONFIGURED", codes)

    def test_crossing_years_fails(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2027, 6, 30),
            end_date_raw=date(2027, 7, 1),
        )
        issue = next(e for e in result.errors if e.code == "CROSSES_FINANCIAL_YEAR")
        self.assertEqual(issue.detail["start_year"], "2026-27")
        self.assertEqual(issue.detail["end_year"], "2027-28")

    def test_single_year_passes_and_labels_context(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertEqual(result.financial_year, "2026-27")


class EligibilityValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_male_not_eligible_for_maternity(self):
        self.stub.register_employee(self.user, gender="M")
        result = run_validation(
            user=self.user,
            leave_type_id=2,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        issue = next(e for e in result.errors if e.code == "NOT_ELIGIBLE")
        self.assertEqual(issue.field, "leave_type")
        self.assertEqual(issue.detail["rule"], "gender")

    def test_female_eligible_for_maternity(self):
        result = run_validation(
            user=self.user,
            leave_type_id=2,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertNotIn("NOT_ELIGIBLE", [e.code for e in result.errors])

    def test_missing_gender_blocks_eligibility(self):
        self.stub.register_employee(self.user, gender=None)
        result = run_validation(
            user=self.user,
            leave_type_id=2,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        issue = next(
            e for e in result.errors if e.code == "ELIGIBILITY_DATA_MISSING"
        )
        self.assertEqual(issue.detail["missing"], "gender")


class DocumentValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def draft(self, **kwargs):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=2,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Maternity leave",
            **kwargs,
        )

    def test_requires_document_blocks_when_none_present(self):
        result = run_validation(
            user=self.user,
            leave_type_id=2,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
            application=self.draft(),
        )
        issue = next(e for e in result.errors if e.code == "DOCUMENT_REQUIRED")
        self.assertEqual(issue.field, "documents")

    def test_with_document_present_passes(self):
        draft = self.draft()
        draft.documents.create(
            file_path="s3://bucket/doc.pdf",
            file_url="https://example.com/doc.pdf",
            file_name="doc.pdf",
            file_size=100,
            content_type="application/pdf",
        )
        result = run_validation(
            user=self.user,
            leave_type_id=2,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
            application=draft,
        )
        self.assertNotIn("DOCUMENT_REQUIRED", [e.code for e in result.errors])


class ReasonValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def test_blank_reason_blocks_submission(self):
        draft = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="  ",
        )
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
            application=draft,
        )
        issue = next(e for e in result.errors if e.code == "REASON_REQUIRED")
        self.assertEqual(issue.field, "reason")


class OverlapValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)
        self.blocking = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=date(2026, 9, 28),
            end_date=date(2026, 10, 2),
            reason="Already away",
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LV-2026-27-000001",
        )

    def test_overlapping_blocking_application_fails(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2026, 9, 29),
            end_date_raw=date(2026, 10, 3),
        )
        issue = next(e for e in result.errors if e.code == "OVERLAPPING_LEAVE")
        self.assertIn("LV-2026-27-000001", issue.message)

    def test_non_overlapping_range_passes(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2026, 10, 5),
            end_date_raw=date(2026, 10, 9),
        )
        self.assertNotIn("OVERLAPPING_LEAVE", [e.code for e in result.errors])

    def test_draft_status_does_not_block(self):
        LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
            reason="Another draft",
        )
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=date(2026, 10, 5),
            end_date_raw=date(2026, 10, 9),
        )
        self.assertNotIn("OVERLAPPING_LEAVE", [e.code for e in result.errors])

    def test_application_never_overlaps_itself(self):
        # The overlap rule must never report an application as overlapping
        # itself: when the very application being validated (here the
        # blocking, submitted one) is passed through, its own row is excluded
        # from the conflicting-applications queryset.
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=self.blocking.start_date,
            end_date_raw=self.blocking.end_date,
            application=self.blocking,
        )
        self.assertNotIn("OVERLAPPING_LEAVE", [e.code for e in result.errors])


class BalanceValidatorTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)
        self.stub.set_balance(self.user.id, "2026-27", Decimal("3"))

    def test_requested_days_over_balance_fails(self):
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),  # 5 working days > 3
        )
        issue = next(e for e in result.errors if e.code == "INSUFFICIENT_BALANCE")
        self.assertEqual(issue.detail["available"], "3")
        self.assertEqual(issue.detail["requested"], 5)

    def test_within_balance_succeeds_and_exposes_numbers(self):
        self.stub.set_balance(self.user.id, "2026-27", Decimal("10"))
        start, end = date(2026, 10, 5), date(2026, 10, 9)  # 5 working days
        result = run_validation(
            user=self.user,
            leave_type_id=1,
            start_date_raw=start,
            end_date_raw=end,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.available_balance, Decimal("10"))
        self.assertEqual(result.balance_after_if_approved, Decimal("5"))

    def test_non_annual_leave_ignores_balance(self):
        result = run_validation(
            user=self.user,
            leave_type_id=4,  # compassionate, does not deduct annual balance
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertNotIn("INSUFFICIENT_BALANCE", [e.code for e in result.errors])


class PreconditionTests(StubProviderMixin, TestCase):
    def test_missing_employee_stops_the_run(self):
        stub = self.use_stub()
        user = make_user()
        result = run_validation(
            user=user,
            leave_type_id=1,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        self.assertEqual(result.skipped_checks, [])
        codes = [e.code for e in result.errors]
        self.assertIn("EMPLOYEE_PROFILE_MISSING", codes)
        self.assertEqual(len(result.errors), 1)

    def test_unavailable_leave_type_stops_the_run(self):
        stub = self.use_stub()
        user = make_user()
        stub.register_employee(user)
        result = run_validation(
            user=user,
            leave_type_id=999,
            start_date_raw=EARLIEST_ANNUAL_START,
            end_date_raw=date(2026, 10, 2),
        )
        codes = [e.code for e in result.errors]
        self.assertIn("LEAVE_TYPE_UNAVAILABLE", codes)
        self.assertEqual(len(result.errors), 1)

    def test_end_before_start_stops_the_run(self):
        stub = self.use_stub()
        user = make_user()
        stub.register_employee(user)
        result = run_validation(
            user=user,
            leave_type_id=1,
            start_date_raw=date(2026, 10, 2),
            end_date_raw=date(2026, 9, 28),
        )
        codes = [e.code for e in result.errors]
        self.assertIn("END_BEFORE_START", codes)
        self.assertEqual(len(result.errors), 1)