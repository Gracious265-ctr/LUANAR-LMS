"""Endpoint tests for the calendar API (§2, §3.7)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import FinancialYear, GradeLeaveEntitlement
from leave_types.models import LeaveType

from calendar_app.models import CalendarEvent, Holiday, WorkingDayPattern

User = get_user_model()

HOLIDAYS = "/api/v1/calendar/holidays/"
WORKING_DAYS = "/api/v1/calendar/working-days/"
FINANCIAL_YEARS = "/api/v1/calendar/financial-years/"
EVENTS = "/api/v1/calendar/events/"


class CalendarApiBase(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@test.luanar", password="pw", role=User.Role.HR
        )
        self.employee = User.objects.create_user(
            username="emp@test.luanar", password="pw", role=User.Role.EMPLOYEE
        )
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user=user)
        return self.client


class AccessTests(CalendarApiBase):
    def test_anonymous_cannot_read(self):
        self.assertEqual(
            self.client.get(HOLIDAYS).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.get(WORKING_DAYS).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_employee_can_read_every_calendar_resource(self):
        self.as_user(self.employee)
        for url in (HOLIDAYS, WORKING_DAYS, FINANCIAL_YEARS, EVENTS):
            self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK, url)

    def test_employee_cannot_write(self):
        self.as_user(self.employee)
        self.assertEqual(
            self.client.post(HOLIDAYS, {"name": "x", "date": "2026-07-06"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.patch(WORKING_DAYS, {"saturday": True}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                FINANCIAL_YEARS, {"start_date": "2026-07-01", "end_date": "2027-06-30"}
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                EVENTS,
                {"title": "Graduation", "start_date": "2026-07-06", "end_date": "2026-07-10"},
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class HolidayApiTests(CalendarApiBase):
    def setUp(self):
        super().setUp()
        self.as_user(self.hr)
        self.holiday = Holiday.objects.create(
            name="Independence Day",
            date=date(2026, 7, 6),
            is_recurring=False,
            observed_shift=False,
        )

    def test_raw_list_is_paginated(self):
        response = self.client.get(HOLIDAYS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Independence Day")

    def test_resolved_list_when_start_and_end_are_given(self):
        Holiday.objects.create(
            name="Christmas", date=date(2020, 12, 25),
            is_recurring=True, observed_shift=False,
        )
        response = self.client.get(
            HOLIDAYS, {"start": "2026-12-20", "end": "2027-01-05"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["date"] for item in response.data], ["2026-12-25"]
        )

    def test_malformed_range_is_400(self):
        response = self.client.get(HOLIDAYS, {"start": "20-12-2026", "end": "2027-01-05"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_requires_a_name_and_date(self):
        response = self.client.post(HOLIDAYS, {"name": "  ", "date": "2027-05-01"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_duplicate_date_and_scope_is_rejected(self):
        response = self.client.post(
            HOLIDAYS, {"name": "Duplicate", "date": "2026-07-06"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date", response.data)

    def test_delete_removes_the_holiday(self):
        response = self.client.delete(f"{HOLIDAYS}{self.holiday.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Holiday.objects.filter(pk=self.holiday.pk).exists())


class WorkingDaysApiTests(CalendarApiBase):
    def test_get_returns_defaults_without_persisting(self):
        self.as_user(self.employee)
        response = self.client.get(WORKING_DAYS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["monday"])
        self.assertTrue(response.data["friday"])
        self.assertFalse(response.data["saturday"])
        self.assertFalse(WorkingDayPattern.objects.exists())

    def test_hr_patch_persists_the_pattern(self):
        self.as_user(self.hr)
        response = self.client.patch(WORKING_DAYS, {"saturday": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["saturday"])
        self.assertTrue(WorkingDayPattern.objects.get().saturday)

    def test_all_days_off_is_rejected(self):
        self.as_user(self.hr)
        response = self.client.patch(
            WORKING_DAYS,
            {
                "monday": False,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": False,
                "sunday": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FinancialYearApiTests(CalendarApiBase):
    def setUp(self):
        super().setUp()
        self.as_user(self.hr)

    def test_hr_can_create_and_employee_can_read(self):
        response = self.client.post(
            FINANCIAL_YEARS,
            {"start_date": "2026-07-01", "end_date": "2027-06-30"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.as_user(self.employee)
        self.assertEqual(self.client.get(FINANCIAL_YEARS).status_code, status.HTTP_200_OK)

    def test_delete_unreferenced_year_succeeds(self):
        year = FinancialYear.objects.create(
            start_date=date(2026, 7, 1), end_date=date(2027, 6, 30)
        )
        response = self.client.delete(f"{FINANCIAL_YEARS}{year.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_referenced_year_is_409(self):
        year = FinancialYear.objects.create(
            start_date=date(2026, 7, 1), end_date=date(2027, 6, 30)
        )
        leave_type = LeaveType.objects.create(name="Annual", code="annual")
        GradeLeaveEntitlement.objects.create(
            grade_id="B", leave_type=leave_type, financial_year=year, days=21
        )
        response = self.client.delete(f"{FINANCIAL_YEARS}{year.pk}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(FinancialYear.objects.filter(pk=year.pk).exists())


class EventApiTests(CalendarApiBase):
    def setUp(self):
        super().setUp()
        self.as_user(self.hr)

    def test_create_event(self):
        response = self.client.post(
            EVENTS,
            {
                "title": "Graduation",
                "start_date": "2026-07-06",
                "end_date": "2026-07-10",
                "description": "Graduation week",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["affects_leave_calculation"])

    def test_end_before_start_is_rejected(self):
        response = self.client.post(
            EVENTS,
            {"title": "Bad", "start_date": "2026-07-10", "end_date": "2026-07-06"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_range_filter_matches_overlapping_events(self):
        CalendarEvent.objects.create(
            title="Orientation", start_date=date(2026, 7, 6), end_date=date(2026, 7, 10)
        )
        response = self.client.get(EVENTS, {"start": "2026-07-08", "end": "2026-07-20"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
