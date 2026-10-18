"""Configured public holidays must actually reduce every leave-day count.

The validation pipeline has always been holiday-aware, but the draft preview and
``preview-days`` used a second, weekend-only counter, so a holiday set by HR could
show up in one number and not the other. These tests pin the whole set of
calculation surfaces to the real ``PublicHoliday`` table through the configured
``DatabaseRulesProvider`` — no stubbed holiday source — so a configured holiday
cannot silently stop counting.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from leave.cancellations.models import LeaveBalanceTransaction
from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    PublicHoliday,
)
from leave_config.models import LeaveType
from workflows.testing import team_for
from leave.services.submission import submit_application
from leave.services.working_days import calculate_working_days, holidays_in_range
from users.models import EmployeeProfile

from .stubs import StubWorkflowProvider, make_user

User = get_user_model()


def _week_shift() -> timedelta:
    """Days to move the fixture week forward to a future Monday.

    Every date below belongs to one frame: a financial year, a working week, and
    a notice period. Shifting the frame as a unit preserves the weekdays and the
    ordering the assertions depend on, while keeping the leave period in the
    future — a request starting today is rejected by ``START_ON_SUBMISSION_DATE``,
    so a fixed calendar frame silently breaks the suite once the clock passes it.
    """
    anchor = date(2026, 9, 28)  # a Monday, the historical start of the fixture week
    today = timezone.localdate()
    # Monday of the week two full weeks from now.
    ahead = today + timedelta(days=14)
    target = ahead - timedelta(days=ahead.weekday())
    return timedelta(days=(target - anchor).days)


SHIFT = _week_shift()


def at(day: date) -> date:
    """A fixture date, moved into the current frame."""
    return day + SHIFT


#: Monday to Friday.
FULL_WEEK_START = at(date(2026, 9, 28))
FULL_WEEK_END = at(date(2026, 10, 2))
FULL_WEEK_DAYS = 5
#: A Wednesday inside that week.
MIDWEEK = at(date(2026, 9, 30))
#: A Saturday inside that week — already excluded as a weekend.
WEEKEND_DAY = at(date(2026, 10, 3))


class PublicHolidayBase(TestCase):
    """Real HR configuration, resolved by the real ``DatabaseRulesProvider``."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password="testpass123",
            role=User.Role.EMPLOYEE,
        )
        EmployeeProfile.objects.create(
            user=self.user,
            team=team_for("Administration Team"),
            designation="Administrative Officer",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
            appointment_date=date(2022, 3, 15),
            gender=EmployeeProfile.Gender.FEMALE,
        )
        self.year = FinancialYear.objects.create(
            start_date=at(date(2026, 7, 1)),
            end_date=at(date(2027, 6, 30)),
            is_active=True,
        )
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=30,
            effective_from=at(date(2026, 1, 1)),
        )
        self.leave_type = LeaveType.objects.create(
            name="Annual",
            code="annual",
            max_duration_days=30,
            notice_days=0,
            consumes_annual_entitlement=True,
        )
        # Only the *rules* provider stays real here, because the public-holiday
        # table is what these tests are about. The approval chain is
        # irrelevant to day counting, so it uses the stub chain.
        self.workflow = StubWorkflowProvider()
        patcher = mock.patch(
            "workflows.providers.get_workflow_provider",
            return_value=self.workflow,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for role in ("supervisor", "hod", "registrar", "dvc"):
            self.workflow.register_approver(role, make_user(f"{role}@test.luanar", role=role))

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def holiday(self, day: date, name: str = "Public Holiday") -> PublicHoliday:
        return PublicHoliday.objects.create(name=name, date=day)

    def draft(self, start=FULL_WEEK_START, end=FULL_WEEK_END):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.leave_type.id,
            start_date=start,
            end_date=end,
            reason="Family visit",
        )

    def create_draft_via_api(self, start=FULL_WEEK_START, end=FULL_WEEK_END):
        """Create through the endpoint, so ``calculated_days`` is written."""
        response = self.client.post(
            "/api/v1/leave-applications/",
            {
                "leave_type_id": self.leave_type.id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "reason": "Family visit",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return LeaveApplication.objects.get(pk=response.data["id"])


class CountWorkingDaysTests(PublicHolidayBase):
    def test_no_holidays_counts_the_whole_week(self):
        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, FULL_WEEK_END), FULL_WEEK_DAYS
        )

    def test_a_configured_holiday_is_not_a_working_day(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")

        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, FULL_WEEK_END),
            FULL_WEEK_DAYS - 1,
        )

    def test_a_holiday_on_a_weekend_is_not_counted_twice(self):
        self.holiday(WEEKEND_DAY, "Weekend holiday")

        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, WEEKEND_DAY), FULL_WEEK_DAYS
        )

    def test_holidays_outside_the_range_do_not_apply(self):
        self.holiday(FULL_WEEK_END + timedelta(days=1))

        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, FULL_WEEK_END), FULL_WEEK_DAYS
        )

    def test_holidays_at_the_range_boundaries_apply(self):
        self.holiday(FULL_WEEK_START, "First day")
        self.holiday(FULL_WEEK_END, "Last day")

        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, FULL_WEEK_END),
            FULL_WEEK_DAYS - 2,
        )

    def test_a_leave_spanning_only_holidays_and_weekends_is_zero(self):
        friday = at(date(2026, 10, 2))
        monday = at(date(2026, 10, 5))
        self.holiday(friday, "Eid al-Fitr")
        self.holiday(monday, "Eid al-Fitr holiday")

        self.assertEqual(calculate_working_days(friday, monday), 0)

    def test_missing_and_reversed_ranges_are_zero(self):
        self.assertEqual(calculate_working_days(None, FULL_WEEK_END), 0)
        self.assertEqual(calculate_working_days(FULL_WEEK_START, None), 0)
        self.assertEqual(calculate_working_days(FULL_WEEK_END, FULL_WEEK_START), 0)

    def test_an_injected_holiday_set_short_circuits_the_provider(self):
        self.holiday(MIDWEEK)

        self.assertEqual(
            calculate_working_days(
                FULL_WEEK_START, FULL_WEEK_END, holidays={MIDWEEK}
            ),
            FULL_WEEK_DAYS - 1,
        )
        self.assertEqual(
            calculate_working_days(FULL_WEEK_START, FULL_WEEK_END, holidays=set()),
            FULL_WEEK_DAYS,
        )


class HolidaysInRangeTests(PublicHolidayBase):
    def test_returns_the_configured_rows_with_their_names(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")
        self.holiday(FULL_WEEK_END + timedelta(days=30), "Christmas Day")

        self.assertEqual(
            holidays_in_range(FULL_WEEK_START, FULL_WEEK_END),
            {MIDWEEK: "Eid al-Fitr"},
        )

    def test_a_reversed_range_is_empty(self):
        self.holiday(MIDWEEK)

        self.assertEqual(holidays_in_range(FULL_WEEK_END, FULL_WEEK_START), {})

    def test_an_unconfigured_calendar_is_empty(self):
        self.assertEqual(holidays_in_range(FULL_WEEK_START, FULL_WEEK_END), {})


class DraftCalculatedDaysTests(PublicHolidayBase):
    """``LeaveApplication.calculated_days`` is the employee's own preview."""

    def test_creating_a_draft_excludes_a_configured_holiday(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")

        app = self.create_draft_via_api()

        self.assertEqual(app.calculated_days, FULL_WEEK_DAYS - 1)

    def test_editing_the_dates_recomputes_and_still_excludes_the_holiday(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")
        app = self.draft()

        response = self.client.patch(
            f"/api/v1/leave-applications/{app.pk}/",
            {
                "start_date": FULL_WEEK_START.isoformat(),
                "end_date": (FULL_WEEK_END + timedelta(days=3)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        app.refresh_from_db()
        # 2026-09-28..2026-10-05 is six weekdays, one of which is the holiday.
        self.assertEqual(app.calculated_days, 6 - 1)

    def test_the_draft_preview_agrees_with_the_validated_count(self):
        """The two day columns on one row must never disagree."""
        self.holiday(MIDWEEK, "Eid al-Fitr")
        app = self.create_draft_via_api()

        submit_application(user=self.user, application_id=app.pk)
        app.refresh_from_db()

        self.assertEqual(app.calculated_days, app.working_days)


class PreviewDaysEndpointTests(PublicHolidayBase):
    url = "/api/v1/leave-applications/preview-days/"

    def post(self, **payload):
        body = {
            "start_date": FULL_WEEK_START.isoformat(),
            "end_date": FULL_WEEK_END.isoformat(),
        }
        body.update(payload)
        return self.client.post(self.url, body, format="json")

    def test_the_preview_excludes_a_configured_holiday(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")

        response = self.post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], FULL_WEEK_DAYS - 1)
        self.assertEqual(response.data["holidays_excluded"], 1)

    def test_the_preview_reports_no_holidays_when_none_are_set(self):
        response = self.post()

        self.assertEqual(response.data["days"], FULL_WEEK_DAYS)
        self.assertEqual(response.data["holidays_excluded"], 0)

    def test_a_holiday_outside_the_range_is_not_reported(self):
        self.holiday(FULL_WEEK_END + timedelta(days=1))

        response = self.post()

        self.assertEqual(response.data["days"], FULL_WEEK_DAYS)
        self.assertEqual(response.data["holidays_excluded"], 0)

    def test_missing_dates_are_400(self):
        self.assertEqual(
            self.post(start_date=None).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_malformed_dates_are_400(self):
        self.assertEqual(
            self.post(start_date="28-09-2026").status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class SubmissionAndDeductionTests(PublicHolidayBase):
    """The configured holiday must reach the frozen count and the ledger."""

    def setUp(self):
        super().setUp()
        self.holiday(MIDWEEK, "Eid al-Fitr")

    def test_submission_freezes_the_holiday_aware_count(self):
        app = self.draft()

        submit_application(user=self.user, application_id=app.pk)
        app.refresh_from_db()

        self.assertEqual(app.working_days, FULL_WEEK_DAYS - 1)
        self.assertEqual(app.calendar_days, FULL_WEEK_DAYS)
        self.assertEqual(
            app.rules_snapshot["holidays"], [MIDWEEK.isoformat()]
        )
        self.assertEqual(
            LeaveApplication.objects.get(pk=app.pk).working_days,
            FULL_WEEK_DAYS - 1,
        )

    def test_finalisation_deducts_the_holiday_aware_days(self):
        from leave.services.finalise import record_deduction

        app = self.draft()
        submit_application(user=self.user, application_id=app.pk)
        app.refresh_from_db()

        transaction = record_deduction(app)

        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.days, FULL_WEEK_DAYS - 1)
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(
                application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
            ).count(),
            1,
        )

    def test_a_holiday_created_after_submission_does_not_re_cut_the_ledger(self):
        """The frozen snapshot wins: HR data changing later cannot rewrite history."""
        app = self.draft()
        submit_application(user=self.user, application_id=app.pk)
        app.refresh_from_db()

        self.holiday(FULL_WEEK_START, "Declared after submission")
        self.holiday(FULL_WEEK_END, "Declared after submission")

        from leave.services.finalise import record_deduction

        transaction = record_deduction(app)

        self.assertEqual(transaction.days, FULL_WEEK_DAYS - 1)

    def test_the_validation_endpoint_reports_the_holiday_aware_count(self):
        response = self.client.post(
            "/api/v1/leave/validate/",
            {
                "leave_type_id": self.leave_type.id,
                "start_date": FULL_WEEK_START.isoformat(),
                "end_date": FULL_WEEK_END.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["working_days"], FULL_WEEK_DAYS - 1)
        self.assertEqual(
            response.data["balance_after_if_approved"],
            str(30 - (FULL_WEEK_DAYS - 1)),
        )

    def test_starting_on_a_configured_holiday_is_rejected(self):
        self.holiday(FULL_WEEK_START, "Eid al-Fitr")

        response = self.client.post(
            "/api/v1/leave/validate/",
            {
                "leave_type_id": self.leave_type.id,
                "start_date": FULL_WEEK_START.isoformat(),
                "end_date": FULL_WEEK_END.isoformat(),
            },
            format="json",
        )

        self.assertFalse(response.data["valid"])
        codes = {error["code"] for error in response.data["errors"]}
        self.assertIn("START_NOT_WORKING_DAY", codes)


class NoticePeriodTests(PublicHolidayBase):
    """``min_notice_days`` is counted in working days, so holidays bite here too."""

    #: A Monday, with the notice window running Tue 22 - Mon 28 September.
    TODAY = at(date(2026, 9, 21))
    START = at(date(2026, 9, 28))
    NOTICE_HOLIDAY = at(date(2026, 9, 23))

    def setUp(self):
        super().setUp()
        LeaveType.objects.filter(pk=self.leave_type.pk).update(notice_days=5)
        patcher = mock.patch(
            "leave.validation.pipeline.get_today", return_value=self.TODAY
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def validate(self):
        response = self.client.post(
            "/api/v1/leave/validate/",
            {
                "leave_type_id": self.leave_type.id,
                "start_date": self.START.isoformat(),
                "end_date": (self.START + timedelta(days=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response

    def test_five_working_days_of_notice_meets_the_rule(self):
        response = self.validate()

        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["working_days"], 3)

    def test_a_holiday_in_the_notice_window_breaks_the_rule(self):
        """A holiday leaves fewer working days to give notice with."""
        self.holiday(self.NOTICE_HOLIDAY, "Eid al-Fitr")

        response = self.validate()

        self.assertFalse(response.data["valid"])
        codes = {error["code"] for error in response.data["errors"]}
        self.assertIn("MIN_NOTICE_NOT_MET", codes)
        # The leave itself is still three working days: the holiday is in the
        # notice window, not in the leave.
        self.assertEqual(response.data["working_days"], 3)


class HolidayChangeRefreshesDraftsTests(PublicHolidayBase):
    """A holiday set after a draft was saved must reach that draft.

    ``calculated_days`` is denormalized, so it is otherwise only as fresh as the
    employee's last edit — the number on their screen would keep excluding
    nothing while the real count excluded the new holiday.
    """

    def setUp(self):
        super().setUp()
        # Two independent weeks, so a holiday can be moved from one to the other.
        self.first = self.create_draft_via_api(
            start=at(date(2026, 9, 28)), end=at(date(2026, 10, 2))
        )
        self.second = self.create_draft_via_api(
            start=at(date(2026, 10, 12)), end=at(date(2026, 10, 16))
        )
        self.assertEqual(self.first.calculated_days, 5)
        self.assertEqual(self.second.calculated_days, 5)

    def stored(self, application):
        application.refresh_from_db()
        return application.calculated_days

    def test_setting_a_holiday_refreshes_an_existing_draft(self):
        self.holiday(MIDWEEK, "Eid al-Fitr")

        self.assertEqual(self.stored(self.first), 4)
        self.assertEqual(self.stored(self.second), 5)

    def test_a_holiday_outside_every_draft_changes_nothing(self):
        self.holiday(at(date(2026, 12, 25)), "Christmas Day")

        self.assertEqual(self.stored(self.first), 5)
        self.assertEqual(self.stored(self.second), 5)

    def test_moving_a_holiday_refreshes_both_the_range_it_left_and_the_one_it_joined(self):
        holiday = self.holiday(MIDWEEK, "Eid al-Fitr")
        self.assertEqual(self.stored(self.first), 4)

        holiday.date = at(date(2026, 10, 14))
        holiday.save()

        self.assertEqual(self.stored(self.first), 5)
        self.assertEqual(self.stored(self.second), 4)

    def test_a_submitted_application_is_never_recounted(self):
        """Frozen at submission: a later holiday must not rewrite history."""
        submitted = self.create_draft_via_api()
        self.assertEqual(submitted.calculated_days, FULL_WEEK_DAYS)
        submit_application(user=self.user, application_id=submitted.pk)
        submitted.refresh_from_db()
        self.assertEqual(submitted.working_days, FULL_WEEK_DAYS)

        self.holiday(MIDWEEK, "Declared after submission")
        self.holiday(FULL_WEEK_END, "Declared after submission")

        submitted.refresh_from_db()
        self.assertEqual(submitted.working_days, FULL_WEEK_DAYS)
        self.assertEqual(submitted.calculated_days, FULL_WEEK_DAYS)

    def test_the_hr_endpoint_path_refreshes_drafts_too(self):
        hr = User.objects.create_user(
            username="hr@test.luanar", password="testpass123", role=User.Role.HR
        )
        client = APIClient()
        client.force_authenticate(user=hr)

        response = client.post(
            "/api/v1/public-holidays/",
            {"name": "Eid al-Fitr", "date": MIDWEEK.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.stored(self.first), 4)
        self.assertEqual(self.stored(self.second), 5)

    def test_a_draft_with_no_dates_is_left_alone(self):
        incomplete = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.leave_type.id,
            reason="Dates not chosen yet",
        )

        self.holiday(MIDWEEK, "Eid al-Fitr")

        incomplete.refresh_from_db()
        self.assertIsNone(incomplete.calculated_days)
