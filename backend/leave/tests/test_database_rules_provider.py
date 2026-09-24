"""Contract tests for the database-backed rules provider (Unit 20).

Every method of :class:`DatabaseRulesProvider` is exercised against real HR
model rows: employees, grade entitlements, leave types/rules (incl. structured
eligibility), financial years, public holidays and the balance ledger.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveBalanceTransaction,
    LeaveRule,
    LeaveType,
    PublicHoliday,
)
from leave.providers.base import EligibilityRule, LeaveBalanceUnavailableError
from leave.providers.database import DatabaseRulesProvider
from users.models import EmployeeProfile, User

TODAY = date(2026, 9, 21)


class DatabaseRulesProviderTests(TestCase):
    def setUp(self):
        self.provider = DatabaseRulesProvider()
        self.user = User.objects.create_user(
            username="employee@test.luanar", password="testpass123"
        )
        EmployeeProfile.objects.create(
            user=self.user,
            department="Administration",
            designation="Administrative Officer",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="b",
            gender=EmployeeProfile.Gender.FEMALE,
            appointment_date=date(2022, 3, 15),
        )
        GradeEntitlement.objects.create(
            grade_start="A", grade_end="C", days=21, effective_from=date(2026, 1, 1)
        )
        self.fy = FinancialYear.objects.create(
            start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_active=True
        )
        PublicHoliday.objects.create(name="Labour Day", date=date(2026, 10, 5))

        self.annual = LeaveType.objects.create(name="Annual Leave", code="annual")
        self.maternity = LeaveType.objects.create(name="Maternity Leave", code="maternity")
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
            eligibility="Female employees at any grade",
            eligibility_rules=[{"type": "gender", "params": {"allowed": ["F"]}}],
            requires_supporting_document=True,
            effective_from=date(2026, 1, 1),
        )

    def test_get_employee_for_user_maps_profile(self):
        info = self.provider.get_employee_for_user(self.user)
        self.assertIsNotNone(info)
        self.assertEqual(info.grade, "B")  # normalized and upper-cased
        self.assertEqual(info.gender, "F")
        self.assertEqual(info.category, "administration")
        self.assertEqual(info.appointment_date, date(2022, 3, 15))
        self.assertIsNone(info.department_id)

    def test_get_employee_for_user_requires_profile(self):
        stranger = User.objects.create_user(
            username="stranger@test.luanar", password="testpass123"
        )
        self.assertIsNone(self.provider.get_employee_for_user(stranger))

    def test_get_employee_for_user_requires_grade_and_appointment(self):
        half = User.objects.create_user(
            username="half@test.luanar", password="testpass123"
        )
        EmployeeProfile.objects.create(user=half, grade="B")
        self.assertIsNone(self.provider.get_employee_for_user(half))

    def test_get_leave_type_rules_maps_effective_rule(self):
        rules = self.provider.get_leave_type_rules(self.maternity.pk, TODAY)
        self.assertIsNotNone(rules)
        self.assertEqual(rules.code, "maternity")
        self.assertEqual(rules.name, "Maternity Leave")
        self.assertTrue(rules.is_active)
        self.assertFalse(rules.deducts_annual_balance)
        self.assertEqual(rules.max_duration, 90)
        self.assertEqual(rules.max_duration_unit, "calendar_days")
        self.assertEqual(rules.min_notice_unit, "working_days")
        self.assertTrue(rules.requires_document)
        self.assertEqual(
            rules.eligibility,
            (EligibilityRule("gender", {"allowed": ["F"]}),),
        )

    def test_get_leave_type_rules_ignore_future_rule(self):
        LeaveRule.objects.create(
            leave_type=self.annual,
            max_duration_days=40,
            eligibility_rules=[{"type": "employee_category", "params": {"allowed": ["academic"]}}],
            effective_from=date(2026, 10, 1),
        )
        rules = self.provider.get_leave_type_rules(self.annual.pk, TODAY)
        self.assertEqual(rules.max_duration, 30)

    def test_get_leave_type_rules_unknown_type_returns_none(self):
        self.assertIsNone(self.provider.get_leave_type_rules(9999, TODAY))

    def test_get_financial_year_for_contains_date(self):
        year = self.provider.get_financial_year_for(date(2026, 11, 1))
        self.assertEqual(year.label, "2026-27")
        self.assertEqual(year.start, date(2026, 7, 1))
        self.assertEqual(year.end, date(2027, 6, 30))

    def test_get_financial_year_for_outside_returns_none(self):
        self.assertIsNone(self.provider.get_financial_year_for(date(2028, 1, 1)))

    def test_get_public_holidays_filters_range(self):
        self.assertEqual(
            self.provider.get_public_holidays(date(2026, 10, 1), date(2026, 10, 9)),
            {date(2026, 10, 5): "Labour Day"},
        )
        self.assertEqual(
            self.provider.get_public_holidays(date(2026, 1, 1), date(2026, 1, 31)),
            {},
        )

    def _application(self):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.annual.pk,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 5),
            status="approved",
        )

    def _transaction(self, days: str, label: str = "2026-27", type="deduction"):
        return LeaveBalanceTransaction.objects.create(
            employee=self.user,
            leave_type=self.annual,
            application=self._application(),
            financial_year=label,
            days=Decimal(days),
            type=type,
        )

    def test_get_available_balance_entitlement_minus_ledger(self):
        label = "2026-27"
        self._transaction("5", label)
        balance = self.provider.get_available_balance(self.user.id, label)
        self.assertEqual(balance, Decimal("16"))

    def test_get_leave_balance_splits_entitlement_used_available(self):
        label = "2026-27"
        self._transaction("5", label)
        balance = self.provider.get_leave_balance(self.user.id, label)
        self.assertEqual(balance.entitlement, 21)
        self.assertEqual(balance.used, 5)
        self.assertEqual(balance.available, 16)

    def test_get_leave_balance_restoration_restores_days(self):
        label = "2026-27"
        self._transaction("5", label, type=LeaveBalanceTransaction.Type.RESTORATION)
        balance = self.provider.get_leave_balance(self.user.id, label)
        self.assertEqual(balance.used, -5)  # net used = -5 (credit)
        self.assertEqual(balance.available, 26)  # entitlement 21 - (-5)

    def test_get_leave_balance_without_entitlement_is_zero(self):
        lonely = User.objects.create_user(
            username="lonely@test.luanar", password="testpass123"
        )
        EmployeeProfile.objects.create(
            user=lonely,
            grade="Z",
            appointment_date=date(2020, 1, 1),
        )
        balance = self.provider.get_leave_balance(lonely.id, "2026-27")
        self.assertEqual((balance.entitlement, balance.used, balance.available), (0, 0, 0))

    def test_get_leave_balance_without_employee_raises(self):
        with self.assertRaises(LeaveBalanceUnavailableError):
            self.provider.get_leave_balance(9999, "2026-27")