"""Unit tests for the calendar resolution services (§3.4–3.5)."""

from datetime import date

from django.test import TestCase

from calendar_app.models import Holiday, WorkingDayPattern
from calendar_app.services import (
    DEFAULT_WORKING_WEEKDAYS,
    get_holidays_for_range,
    get_working_day_pattern,
    holidays_map,
    working_weekdays,
)


class WorkingWeekdaysTests(TestCase):
    def test_absent_pattern_is_monday_to_friday(self):
        self.assertIsNone(get_working_day_pattern())
        self.assertEqual(working_weekdays(), set(DEFAULT_WORKING_WEEKDAYS))

    def test_saved_pattern_overrides_the_default(self):
        WorkingDayPattern.objects.create(saturday=True, sunday=True)
        self.assertEqual(working_weekdays(), {0, 1, 2, 3, 4, 5, 6})

    def test_weekday_flags_map_to_the_right_indices(self):
        WorkingDayPattern.objects.create(
            monday=False, tuesday=False, wednesday=False, thursday=False,
            friday=False, saturday=True, sunday=False,
        )
        self.assertEqual(working_weekdays(), {5})


class HolidayResolutionTests(TestCase):
    def test_one_off_holiday_inside_range_is_returned(self):
        Holiday.objects.create(
            name="Independence Day",
            date=date(2026, 7, 6),
            is_recurring=False,
            observed_shift=False,
        )
        resolved = get_holidays_for_range(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual([(r.date, r.holiday.name) for r in resolved],
                         [(date(2026, 7, 6), "Independence Day")])

    def test_one_off_holiday_outside_range_is_excluded(self):
        Holiday.objects.create(
            name="Christmas", date=date(2026, 12, 25),
            is_recurring=False, observed_shift=False,
        )
        self.assertEqual(
            get_holidays_for_range(date(2026, 7, 1), date(2026, 7, 31)), []
        )

    def test_recurring_holiday_resolves_across_a_year_boundary(self):
        Holiday.objects.create(
            name="Christmas", date=date(2020, 12, 25),
            is_recurring=True, observed_shift=False,
        )
        Holiday.objects.create(
            name="New Year", date=date(2020, 1, 1),
            is_recurring=True, observed_shift=False,
        )

        resolved = get_holidays_for_range(date(2026, 12, 20), date(2027, 1, 5))

        self.assertEqual(
            [r.date for r in resolved], [date(2026, 12, 25), date(2027, 1, 1)]
        )

    def test_observed_shift_moves_a_saturday_holiday_to_monday(self):
        # 2026-10-03 is a Saturday; Mon-Fri is the default working week.
        Holiday.objects.create(
            name="Weekend holiday", date=date(2026, 10, 3),
            is_recurring=False, observed_shift=True,
        )
        resolved = get_holidays_for_range(date(2026, 10, 1), date(2026, 10, 10))
        self.assertEqual([r.date for r in resolved], [date(2026, 10, 5)])

    def test_observed_shift_disabled_keeps_the_weekend_date(self):
        Holiday.objects.create(
            name="Weekend holiday", date=date(2026, 10, 3),
            is_recurring=False, observed_shift=False,
        )
        resolved = get_holidays_for_range(date(2026, 10, 1), date(2026, 10, 10))
        self.assertEqual([r.date for r in resolved], [date(2026, 10, 3)])

    def test_observed_shift_uses_the_configured_pattern(self):
        # Saturday is a working day, so a Saturday holiday is not shifted.
        WorkingDayPattern.objects.create(saturday=True)
        Holiday.objects.create(
            name="Saturday holiday", date=date(2026, 10, 3),
            is_recurring=False, observed_shift=True,
        )
        resolved = get_holidays_for_range(date(2026, 10, 1), date(2026, 10, 10))
        self.assertEqual([r.date for r in resolved], [date(2026, 10, 3)])

    def test_holidays_map_keys_by_resolved_date(self):
        Holiday.objects.create(
            name="Independence Day", date=date(2026, 7, 6),
            is_recurring=False, observed_shift=False,
        )
        self.assertEqual(
            holidays_map(date(2026, 7, 1), date(2026, 7, 31)),
            {date(2026, 7, 6): "Independence Day"},
        )

    def test_feb_29_reference_is_skipped_in_non_leap_years(self):
        Holiday.objects.create(
            name="Leap Day", date=date(2020, 2, 29),
            is_recurring=True, observed_shift=False,
        )
        # 2027 is not a leap year: nothing resolves rather than raising.
        self.assertEqual(
            get_holidays_for_range(date(2027, 2, 1), date(2027, 3, 1)), []
        )
        # 2028 is a leap year.
        resolved = get_holidays_for_range(date(2028, 2, 1), date(2028, 3, 1))
        self.assertEqual([r.date for r in resolved], [date(2028, 2, 29)])
