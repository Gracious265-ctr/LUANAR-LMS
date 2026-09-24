"""Tests for the employee "my data" endpoints (Unit 20)."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveBalanceTransaction,
    LeaveRule,
    LeaveType,
)
from users.models import EmployeeProfile, User


class MyLeaveViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="employee@test.luanar", password="testpass123"
        )
        EmployeeProfile.objects.create(
            user=self.user,
            department="Administration",
            designation="Administrative Officer",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
            gender=EmployeeProfile.Gender.FEMALE,
            appointment_date=date(2022, 3, 15),
        )
        GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=21, effective_from=date(2026, 1, 1)
        )
        FinancialYear.objects.create(
            start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_active=True
        )
        self.annual = LeaveType.objects.create(name="Annual Leave", code="annual")
        self.maternity = LeaveType.objects.create(name="Maternity Leave", code="maternity")
        self.unconfigured = LeaveType.objects.create(name="Study Leave", code="study-leave")
        LeaveRule.objects.create(
            leave_type=self.annual,
            max_duration_days=30,
            min_notice_days=5,
            consumes_annual_entitlement=True,
            effective_from=date(2026, 1, 1),
        )
        LeaveRule.objects.create(
            leave_type=self.maternity,
            max_duration_days=90,
            requires_supporting_document=True,
            eligibility_rules=[{"type": "gender", "params": {"allowed": ["F"]}}],
            effective_from=date(2026, 1, 1),
        )

    def test_overview_requires_authentication(self):
        self.client.logout()
        response = self.client.get("/api/v1/leave/my/overview/")
        self.assertIn(response.status_code, (401, 403))

    def test_overview_returns_profile_and_balance(self):
        application = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.annual.pk,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
            status="pending",
        )
        LeaveBalanceTransaction.objects.create(
            employee=self.user,
            leave_type=self.annual,
            application=application,
            financial_year="2026-27",
            days=Decimal("5"),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/leave/my/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.data

        self.assertEqual(data["profile"]["grade"], "B")
        self.assertEqual(data["profile"]["gender"], "F")
        self.assertEqual(data["profile"]["department"], "Administration")
        self.assertEqual(data["profile"]["appointment_date"], "2022-03-15")
        self.assertEqual(data["financial_year"]["label"], "2026-27")
        self.assertEqual(data["entitlement"], 21)
        self.assertEqual(data["used"], 5)
        self.assertEqual(data["available"], 16)
        self.assertEqual(data["pending_applications"], 1)
        self.assertEqual(data["upcoming_leaves"], 0)
        self.assertIsNone(data["next_leave_start"])

    def test_overview_counts_upcoming_approved_leave(self):
        LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.annual.pk,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
            status="approved",
        )
        self.client.force_authenticate(user=self.user)
        data = self.client.get("/api/v1/leave/my/overview/").data
        self.assertEqual(data["upcoming_leaves"], 1)
        self.assertEqual(data["next_leave_start"], "2026-12-01")

    def test_overview_null_balance_without_profile(self):
        stranger = User.objects.create_user(
            username="stranger@test.luanar", password="testpass123"
        )
        self.client.force_authenticate(user=stranger)
        data = self.client.get("/api/v1/leave/my/overview/").data
        self.assertIsNone(data["profile"])
        self.assertIsNone(data["entitlement"])
        self.assertIsNone(data["available"])

    def test_my_leave_types_returns_configured_types_only(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/leave/my/leave-types/")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data]
        self.assertEqual(names, ["Annual Leave", "Maternity Leave"])
        self.assertNotIn("Study Leave", names)

        maternity = next(item for item in response.data if item["code"] == "maternity")
        self.assertTrue(maternity["requires_supporting_document"])
        self.assertEqual(maternity["max_duration_days"], 90)
        self.assertFalse(maternity["consumes_annual_entitlement"])
        self.assertEqual(
            maternity["eligibility"],
            [{"type": "gender", "params": {"allowed": ["F"]}}],
        )