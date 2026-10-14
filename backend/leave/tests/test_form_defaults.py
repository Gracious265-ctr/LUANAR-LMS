"""``GET /api/v1/leave/me/form-defaults/`` — the form's warm-start values.

The endpoint is deliberately forgiving: an employee with no history still gets a
usable start date and the canonical annual type, and an unconfigured year yields
an empty balance map rather than an error. These tests pin both the happy path
and each graceful degradation, because the form reads every field without a
fallback of its own.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
)
from users.models import EmployeeProfile

from .stubs import make_user

User = get_user_model()

URL = "/api/v1/leave/me/form-defaults/"


class FormDefaultsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = make_user("defaults-owner@luanar")
        EmployeeProfile.objects.create(user=self.owner, grade="B")
        self.client.force_authenticate(user=self.owner)

    def annual_type(self):
        return LeaveType.objects.create(name="Annual Leave", code="annual")

    def leave_type(self, code, *, consumes, **rule_fields):
        leave_type = LeaveType.objects.create(name=code.title(), code=code)
        LeaveRule.objects.create(
            leave_type=leave_type,
            max_duration_days=rule_fields.pop("max_duration_days", 30),
            consumes_annual_entitlement=consumes,
            effective_from=rule_fields.pop("effective_from", date(2020, 1, 1)),
            **rule_fields,
        )
        return leave_type

    def active_year(self):
        return FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

    def get(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_requires_authentication(self):
        response = APIClient().get(URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_latest_application_type_wins(self):
        self.leave_type("maternity", consumes=False)
        study = self.leave_type("study", consumes=False)
        annual = self.annual_type()

        LeaveApplication.objects.create(employee=self.owner, leave_type_id=annual.id)
        latest = LeaveApplication.objects.create(
            employee=self.owner, leave_type_id=study.id
        )
        # Make the ordering explicit rather than relying on insertion order.
        LeaveApplication.objects.filter(pk=latest.pk).update(
            created_at="2099-01-01T00:00:00Z"
        )

        self.assertEqual(self.get()["last_leave_type_id"], study.id)

    def test_cancelled_applications_are_ignored_for_the_default(self):
        annual = self.annual_type()
        other = self.leave_type("maternity", consumes=False)

        LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=other.id,
            status=LeaveApplication.Status.CANCELLED,
        )

        # The cancelled application must not become the default; without a live
        # history the canonical annual type is the fallback.
        self.assertEqual(self.get()["last_leave_type_id"], annual.id)

    def test_falls_back_to_the_annual_type_without_history(self):
        annual = self.annual_type()
        self.assertEqual(self.get()["last_leave_type_id"], annual.id)

    def test_no_annual_type_and_no_history_yields_null(self):
        self.assertIsNone(self.get()["last_leave_type_id"])

    def test_default_start_date_is_a_working_day(self):
        payload = self.get()
        start = payload["default_start_date"]
        self.assertLess(date.today(), start)
        self.assertLess(start.weekday(), 5)

    @patch("leave.views.me.get_today")
    def test_default_start_date_skips_weekends_and_holidays(self, today):
        today.return_value = date(2026, 10, 9)  # Friday
        PublicHoliday.objects.create(date=date(2026, 10, 12), name="Bridge day")

        payload = self.get()

        # Friday -> weekend -> holiday Monday -> Tuesday.
        self.assertEqual(payload["default_start_date"], date(2026, 10, 13))

    def test_balance_by_type_covers_annual_types_only(self):
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=date(2020, 1, 1),
        )
        self.active_year()
        annual = self.leave_type("annual", consumes=True)
        self.leave_type("maternity", consumes=False)

        payload = self.get()

        self.assertEqual(payload["balance_by_type"], {str(annual.id): "21"})

    def test_balance_by_type_is_empty_without_an_active_year(self):
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=date(2020, 1, 1),
        )
        self.leave_type("annual", consumes=True)

        self.assertEqual(self.get()["balance_by_type"], {})
