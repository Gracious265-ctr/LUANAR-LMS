"""The calendar is consumed by leave's day-counting (§3.4, §3.8).

These tests pin the seam: the working-day pattern and resolved holidays reach
``calculate_working_days`` and the draft-refresh signals.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from leave.models import LeaveApplication
from leave.services.working_days import calculate_working_days
from leave.validation.working_days import configured_weekdays, count_working_days
from leave_types.models import LeaveType

from calendar_app.models import Holiday, WorkingDayPattern

User = get_user_model()

MONDAY = date(2026, 9, 28)
SATURDAY = date(2026, 10, 3)
MIDWEEK = date(2026, 9, 30)


class PatternAwareCountingTests(TestCase):
    def test_default_week_counts_monday_to_friday(self):
        self.assertEqual(calculate_working_days(MONDAY, SATURDAY), 5)

    def test_configured_saturday_is_counted(self):
        WorkingDayPattern.objects.create(saturday=True)
        self.assertEqual(calculate_working_days(MONDAY, SATURDAY), 6)

    def test_configured_weekday_off_is_excluded(self):
        WorkingDayPattern.objects.create(wednesday=False)
        self.assertEqual(
            count_working_days(MONDAY, date(2026, 10, 2), set(), configured_weekdays()),
            4,
        )


class PatternChangeRefreshesDraftsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="emp@test.luanar", password="pw", role=User.Role.EMPLOYEE
        )
        self.leave_type = LeaveType.objects.create(name="Annual", code="annual")
        self.draft = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.leave_type.id,
            start_date=MONDAY,
            end_date=SATURDAY,
            reason="Family visit",
            calculated_days=5,
        )

    def test_saving_a_pattern_refreshes_live_drafts(self):
        WorkingDayPattern.objects.create(saturday=True)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.calculated_days, 6)


class HolidayDeleteRefreshesDraftsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="emp@test.luanar", password="pw", role=User.Role.EMPLOYEE
        )
        self.leave_type = LeaveType.objects.create(name="Annual", code="annual")
        self.holiday = Holiday.objects.create(
            name="Eid", date=MIDWEEK, is_recurring=False, observed_shift=False
        )
        self.draft = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.leave_type.id,
            start_date=MONDAY,
            end_date=SATURDAY,
            reason="Family visit",
            calculated_days=4,
        )

    def test_deleting_a_holiday_recounts_the_draft(self):
        self.holiday.delete()
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.calculated_days, 5)
