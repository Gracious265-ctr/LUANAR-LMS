"""Unit tests for the database-backed rules provider (Unit 20).

Verifies that :class:`~leave.providers.database.DatabaseRulesProvider` resolves
the five ``RulesProvider`` protocol methods from the real HR-track tables and
never invents data: absent configuration degrades to ``None``/``{}``/``0``.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from calendar_app.models import Holiday
from leave.cancellations.models import LeaveBalanceTransaction
from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
)
from leave_types.models import LeaveType
from chains.testing import team_for
from leave.providers.database import DatabaseRulesProvider
from users.models import EmployeeProfile

User = get_user_model()

Grade = EmployeeProfile.Category


class ProviderSetupMixin:
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password="testpass123",
        )
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            team=team_for("Administration Team"),
            designation="Administrative Officer",
            category=Grade.ADMINISTRATION,
            grade="B",
            appointment_date=date(2022, 3, 15),
            gender=EmployeeProfile.Gender.FEMALE,
        )
        self.provider = DatabaseRulesProvider()


class GetEmployeeForUserTests(ProviderSetupMixin, TestCase):
    def test_returns_mapped_employee_info(self):
        info = self.provider.get_employee_for_user(self.user)

        self.assertIsNotNone(info)
        self.assertEqual(info.id, self.user.id)
        self.assertEqual(info.user_id, self.user.id)
        self.assertEqual(info.grade, "B")
        self.assertEqual(info.appointment_date, date(2022, 3, 15))
        self.assertEqual(info.category, "administration")
        self.assertEqual(info.gender, "F")

    def test_absent_profile_returns_none(self):
        other = User.objects.create_user(username="no-profile", password="x")
        self.assertIsNone(self.provider.get_employee_for_user(other))

    def test_blank_grade_returns_none(self):
        self.profile.grade = "   "
        self.profile.save()
        self.assertIsNone(self.provider.get_employee_for_user(self.user))

    def test_missing_appointment_date_maps_to_none(self):
        # The column is nullable, so a profile without one is still a profile:
        # returning None here would make submission claim no profile exists.
        self.profile.appointment_date = None
        self.profile.save()
        info = self.provider.get_employee_for_user(self.user)

        self.assertIsNotNone(info)
        self.assertIsNone(info.appointment_date)


class GetLeaveTypeRulesTests(ProviderSetupMixin, TestCase):
    def _make_leave_type(self, code, **rule_fields):
        # Refinement unit 06 folded the effective-dated rule into the type, so
        # the fields the provider reads are written straight onto the row.
        rule_fields.setdefault("max_duration_days", 10)
        return LeaveType.objects.create(name=code.title(), code=code, **rule_fields)

    def test_annual_is_measured_in_working_days(self):
        leave_type = self._make_leave_type(
            "annual",
            max_duration_days=30,
            notice_days=5,
            consumes_annual_entitlement=True,
        )

        rules = self.provider.get_leave_type_rules(leave_type.id, date(2026, 9, 21))

        self.assertIsNotNone(rules)
        self.assertEqual(rules.code, "annual")
        self.assertEqual(rules.deducts_annual_balance, True)
        self.assertEqual(rules.max_duration, 30)
        self.assertEqual(rules.max_duration_unit, "working_days")
        self.assertEqual(rules.min_notice, 5)
        self.assertEqual(rules.min_notice_unit, "working_days")

    def test_other_types_are_measured_in_calendar_days(self):
        leave_type = self._make_leave_type(
            "maternity", max_duration_days=90, requires_supporting_document=True
        )

        rules = self.provider.get_leave_type_rules(leave_type.id, date(2026, 9, 21))

        self.assertEqual(rules.max_duration_unit, "calendar_days")
        self.assertEqual(rules.min_notice_unit, "calendar_days")
        self.assertEqual(rules.requires_document, True)

    def test_eligibility_rules_are_parsed_from_json(self):
        leave_type = self._make_leave_type(
            "paternity",
            eligibility_rules=[{"type": "gender", "params": {"allowed": ["M"]}}],
        )

        rules = self.provider.get_leave_type_rules(leave_type.id, date(2026, 9, 21))

        self.assertEqual(len(rules.eligibility), 1)
        rule = rules.eligibility[0]
        self.assertEqual(rule.type, "gender")
        self.assertEqual(rule.params, {"allowed": ["M"]})

    def test_effective_dating_is_retired_so_any_as_of_answers(self):
        # The ``LeaveRule`` date dimension is gone (§4.2): a type that exists
        # answers for any date, and only its own ``is_active`` gate applies.
        leave_type = self._make_leave_type("compassionate")
        rules = self.provider.get_leave_type_rules(leave_type.id, date(2025, 12, 31))

        self.assertIsNotNone(rules)
        self.assertTrue(rules.is_active)

    def test_deactivated_type_carries_its_flag_instead_of_disappearing(self):
        # Deactivation (§1.5) hides a type from new selections without taking
        # the policy away from applications already filed against it, so the
        # provider still answers — just flagged. The catalog, not the evaluator,
        # is what stops offering the type.
        leave_type = self._make_leave_type("compassionate")
        LeaveType.objects.filter(pk=leave_type.pk).update(is_active=False)

        rules = self.provider.get_leave_type_rules(leave_type.id, date(2026, 9, 21))

        self.assertIsNotNone(rules)
        self.assertFalse(rules.is_active)

    def test_unknown_leave_type_returns_none(self):
        self.assertIsNone(self.provider.get_leave_type_rules(999999, date(2026, 9, 21)))


class GetFinancialYearTests(ProviderSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.year = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

    def test_inline_date_returns_labeled_year(self):
        year = self.provider.get_financial_year_for(date(2026, 9, 21))

        self.assertIsNotNone(year)
        self.assertEqual(year.label, "2026-27")
        self.assertEqual(year.start, date(2026, 7, 1))
        self.assertEqual(year.end, date(2027, 6, 30))

    def test_outside_any_year_returns_none(self):
        self.assertIsNone(self.provider.get_financial_year_for(date(2025, 1, 1)))


class GetPublicHolidaysTests(ProviderSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        Holiday.objects.create(
            name="In range", date=date(2026, 9, 30), is_recurring=False, observed_shift=False
        )
        Holiday.objects.create(
            name="Outside", date=date(2026, 12, 25), is_recurring=False, observed_shift=False
        )

    def test_only_rows_in_range_are_returned(self):
        holidays = self.provider.get_public_holidays(
            date(2026, 9, 1), date(2026, 9, 30)
        )

        self.assertEqual(holidays, {date(2026, 9, 30): "In range"})


class GetAvailableBalanceTests(ProviderSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=date(2026, 1, 1),
        )

    def _application_for(self, label="2026-27"):
        return LeaveApplication.objects.create(
            employee=self.user,
            start_date=date(2026, 9, 28),
            end_date=date(2026, 10, 2),
            working_days=5,
            financial_year_label=label,
        )

    def test_balance_is_entitlement_plus_ledger_net(self):
        LeaveBalanceTransaction.objects.create(
            employee=self.user,
            financial_year="2026-27",
            leave_type=1,
            application=self._application_for(),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal("3"),
        )
        LeaveBalanceTransaction.objects.create(
            employee=self.user,
            financial_year="2026-27",
            leave_type=1,
            application=self._application_for(),
            type=LeaveBalanceTransaction.Type.RESTORATION,
            days=Decimal("1"),
        )

        balance = self.provider.get_available_balance(self.user.id, "2026-27")

        self.assertEqual(balance, Decimal("19"))

    def test_balance_clamps_at_zero(self):
        LeaveBalanceTransaction.objects.create(
            employee=self.user,
            financial_year="2026-27",
            leave_type=1,
            application=self._application_for(),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal("25"),
        )

        self.assertEqual(self.provider.get_available_balance(self.user.id, "2026-27"), Decimal("0"))

    def test_ledger_is_financial_year_scoped(self):
        LeaveBalanceTransaction.objects.create(
            employee=self.user,
            financial_year="2025-26",
            leave_type=1,
            application=self._application_for("2025-26"),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal("20"),
        )

        self.assertEqual(self.provider.get_available_balance(self.user.id, "2026-27"), Decimal("21"))

    def test_missing_profile_returns_zero(self):
        other = User.objects.create_user(username="no-profile", password="x")
        self.assertEqual(self.provider.get_available_balance(other.id, "2026-27"), Decimal("0"))


class LeaveSummaryEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("leave:leave-me-summary"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_degrades_gracefully_without_profile(self):
        response = self.client.get(reverse("leave:leave-me-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["profile"])
        self.assertIsNone(response.data["entitlement"])
        self.assertIsNone(response.data["financial_year"])
        self.assertIsNone(response.data["available_balance"])

    def test_summary_reflects_hr_record(self):
        EmployeeProfile.objects.create(
            user=self.user,
            team=team_for("Administration Team"),
            designation="Administrative Officer",
            category=Grade.ADMINISTRATION,
            grade="B",
            appointment_date=date(2022, 3, 15),
            gender=EmployeeProfile.Gender.FEMALE,
        )
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=date(2026, 1, 1),
        )
        FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

        response = self.client.get(reverse("leave:leave-me-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["grade"], "B")
        self.assertEqual(response.data["profile"]["gender"], "F")
        self.assertEqual(response.data["entitlement"]["days"], 21)
        self.assertEqual(response.data["financial_year"]["label"], "2026-27")
        self.assertEqual(response.data["available_balance"], "21")