"""Unit tests for ``leave.validation.working_days`` (calendar helpers)."""

from datetime import date

from django.test import SimpleTestCase

from leave.validation.working_days import (
    count_calendar_days,
    count_working_days,
    is_weekend,
    is_working_day,
    working_days_elapsed,
)

from .stubs import HOLIDAY, TODAY


class IsWeekendTests(SimpleTestCase):
    def test_fridays_are_not_weekends(self):
        self.assertFalse(is_weekend(date(2026, 9, 25)))

    def test_saturdays_and_sundays_are_weekends(self):
        self.assertTrue(is_weekend(date(2026, 9, 26)))
        self.assertTrue(is_weekend(date(2026, 9, 27)))

    def test_monday_is_not_a_weekend(self):
        self.assertFalse(is_weekend(TODAY))


class IsWorkingDayTests(SimpleTestCase):
    def test_plain_weekday_is_a_working_day(self):
        self.assertTrue(is_working_day(date(2026, 9, 22), set()))

    def test_holiday_is_not_a_working_day(self):
        self.assertFalse(is_working_day(HOLIDAY, {HOLIDAY}))

    def test_weekend_holiday_is_not_a_working_day(self):
        self.assertFalse(is_working_day(date(2026, 9, 26), set()))


class CountWorkingDaysTests(SimpleTestCase):
    def test_monday_friday_is_five(self):
        start, end = date(2026, 9, 21), date(2026, 9, 25)
        self.assertEqual(count_working_days(start, end, set()), 5)

    def test_holiday_in_range_is_excluded(self):
        # 2026-09-30 is a Wednesday placeholder holiday.
        start, end = date(2026, 9, 28), date(2026, 10, 2)
        self.assertEqual(count_working_days(start, end, set()), 5)
        self.assertEqual(count_working_days(start, end, {HOLIDAY}), 4)

    def test_reversed_range_is_zero(self):
        self.assertEqual(
            count_working_days(date(2026, 9, 25), date(2026, 9, 21), set()), 0
        )

    def test_single_day(self):
        self.assertEqual(count_working_days(date(2026, 9, 22), date(2026, 9, 22), set()), 1)


class CountCalendarDaysTests(SimpleTestCase):
    def test_inclusive_single_day(self):
        self.assertEqual(count_calendar_days(date(2026, 9, 22), date(2026, 9, 22)), 1)

    def test_full_week_is_seven(self):
        self.assertEqual(
            count_calendar_days(date(2026, 9, 21), date(2026, 9, 27)), 7
        )

    def test_reversed_range_is_zero(self):
        self.assertEqual(
            count_calendar_days(date(2026, 9, 27), date(2026, 9, 21)), 0
        )


class WorkingDaysElapsedTests(SimpleTestCase):
    def test_five_working_days_to_next_monday(self):
        # From Monday 21 Sep to Monday 28 Sep: Tue-Fri + Mon = 5.
        self.assertEqual(
            working_days_elapsed(TODAY, date(2026, 9, 28), set()), 5
        )

    def test_tomorrow_counts_as_one(self):
        self.assertEqual(working_days_elapsed(TODAY, date(2026, 9, 22), set()), 1)

    def test_same_day_is_zero(self):
        self.assertEqual(working_days_elapsed(TODAY, TODAY, set()), 0)

    def test_holiday_is_not_counted(self):
        # From Monday 21 Sep: Tue, Wed(holiday), Thu, Fri = 4 not 5.
        self.assertEqual(
            working_days_elapsed(TODAY, date(2026, 9, 25), {HOLIDAY}), 4
        )