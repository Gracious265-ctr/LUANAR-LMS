"""Rejected-leave carry-over: amount, rollover writer, and the command.

Rules under test (``context/project-overview.md``):

* only days a *rejection* left unused are carried
  (``carried = min(rejected, entitlement - consumed)``);
* ordinary unused entitlement is **not** carried — it resets;
* ``correction_required`` is a soft return and never carries;
* the rollover is idempotent and the provider funds the recipient year only.
"""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveCarryOver,
)
from leave.cancellations.models import LeaveBalanceTransaction
from leave.providers.database import DatabaseRulesProvider
from leave.services.carry_over import carry_over_amount, carry_over_financial_year
from users.models import EmployeeProfile
from workflows.testing import team_for

User = get_user_model()

Grade = EmployeeProfile.Category


class CarryOverSetupMixin:
    def setUp(self):
        super().setUp()
        # Grade B → 21 days (A–C band), effective before the closing year.
        GradeEntitlement.objects.create(
            grade_start="A",
            grade_end="C",
            days=21,
            effective_from=date(2025, 1, 1),
        )
        self.closing = FinancialYear.objects.create(
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=True,
        )
        self.opening = FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
        )
        self.closing_label = "2025-26"
        self.opening_label = "2026-27"

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

    def _application(self, *, status, days, label=None):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 5),
            working_days=days,
            financial_year_label=label or self.closing_label,
            status=status,
        )

    def _deduction(self, days, *, application=None, label=None):
        return LeaveBalanceTransaction.objects.create(
            employee=self.user,
            financial_year=label or self.closing_label,
            leave_type=1,
            application=application or self._application(
                status=LeaveApplication.Status.APPROVED, days=int(days)
            ),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal(days),
        )


class CarryOverAmountTests(CarryOverSetupMixin, TestCase):
    def test_no_rejected_applications_carries_nothing(self):
        self._application(
            status=LeaveApplication.Status.APPROVED, days=5
        )

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(0)
        )

    def test_rejected_days_carry_when_untouched(self):
        # 4 rejected days, nothing consumed → all 4 carry.
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(4)
        )

    def test_only_rejected_status_carries(self):
        # A pending or approved application never carries; only hard rejections.
        self._application(status=LeaveApplication.Status.SUBMITTED, days=6)
        self._application(status=LeaveApplication.Status.DRAFT, days=6)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(0)
        )

    def test_carried_rejected_days_are_capped_by_unused_entitlement(self):
        # 21 entitlement, 18 consumed → only 3 genuinely left; even though 10
        # days were rejected, only 3 are unused and therefore carried.
        self._deduction(Decimal("18"))
        self._application(status=LeaveApplication.Status.REJECTED, days=10)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(3)
        )

    def test_rejected_days_are_the_upper_bound_when_entitlement_is_larger(self):
        # 21 entitlement, 2 consumed → 19 unused, but only 4 rejected → 4.
        self._deduction(Decimal("2"))
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(4)
        )

    def test_over_consumption_clamps_carry_to_zero(self):
        self._deduction(Decimal("25"))
        self._application(status=LeaveApplication.Status.REJECTED, days=5)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(0)
        )

    def test_rejected_days_in_another_year_do_not_count(self):
        self._application(
            status=LeaveApplication.Status.REJECTED,
            days=7,
            label=self.opening_label,
        )

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(0)
        )

    def test_other_employees_deductions_do_not_count(self):
        other = User.objects.create_user(username="other@test.luanar", password="x")
        EmployeeProfile.objects.create(
            user=other,
            team=team_for("Administration Team"),
            designation="Officer",
            category=Grade.ADMINISTRATION,
            grade="B",
            appointment_date=date(2022, 3, 15),
        )
        LeaveBalanceTransaction.objects.create(
            employee=other,
            financial_year=self.closing_label,
            leave_type=1,
            application=LeaveApplication.objects.create(
                employee=other,
                working_days=18,
                financial_year_label=self.closing_label,
                status=LeaveApplication.Status.APPROVED,
            ),
            type=LeaveBalanceTransaction.Type.DEDUCTION,
            days=Decimal("18"),
        )
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        self.assertEqual(
            carry_over_amount(self.user.id, self.closing), Decimal(4)
        )


class CarryOverWriterTests(CarryOverSetupMixin, TestCase):
    def test_writes_one_row_naming_the_recipient_year(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        results = carry_over_financial_year(self.closing, self.opening)

        self.assertEqual(len(results), 1)
        row = LeaveCarryOver.objects.get(employee=self.user)
        self.assertEqual(row.from_financial_year, self.closing_label)
        self.assertEqual(row.to_financial_year, self.opening_label)
        self.assertEqual(row.days, Decimal("4"))

    def test_is_idempotent(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        carry_over_financial_year(self.closing, self.opening)
        second = carry_over_financial_year(self.closing, self.opening)

        self.assertEqual(LeaveCarryOver.objects.count(), 1)
        self.assertFalse(second[0]["created"])

    def test_dry_run_writes_nothing(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        results = carry_over_financial_year(
            self.closing, self.opening, dry_run=True
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days"], Decimal("4"))
        self.assertFalse(LeaveCarryOver.objects.exists())

    def test_skips_employees_with_nothing_to_carry(self):
        self._deduction(Decimal("25"))
        self._application(status=LeaveApplication.Status.REJECTED, days=5)

        results = carry_over_financial_year(self.closing, self.opening)

        self.assertEqual(results, [])
        self.assertFalse(LeaveCarryOver.objects.exists())

    def test_provider_funds_the_recipient_year_by_the_carried_amount(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)
        carry_over_financial_year(self.closing, self.opening)

        provider = DatabaseRulesProvider()

        self.assertEqual(
            provider.get_available_balance(self.user.id, self.opening_label),
            Decimal("25"),
        )
        # The closing year is unchanged: carry-over is not normal rollover.
        self.assertEqual(
            provider.get_available_balance(self.user.id, self.closing_label),
            Decimal("21"),
        )


class CarryOverCommandTests(CarryOverSetupMixin, TestCase):
    def test_rolls_active_year_into_the_next_configured_year(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        out = StringIO()
        call_command("carry_over_leave", stdout=out)

        row = LeaveCarryOver.objects.get(employee=self.user)
        self.assertEqual(row.to_financial_year, self.opening_label)
        self.assertEqual(row.days, Decimal("4"))

    def test_dry_run_reports_without_writing(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        out = StringIO()
        call_command("carry_over_leave", "--dry-run", stdout=out)

        self.assertFalse(LeaveCarryOver.objects.exists())
        self.assertIn("Would carry", out.getvalue())

    def test_explicit_from_and_to_labels(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)

        out = StringIO()
        call_command(
            "carry_over_leave",
            from_label=self.closing_label,
            to_label=self.opening_label,
            stdout=out,
        )

        self.assertTrue(
            LeaveCarryOver.objects.filter(
                to_financial_year=self.opening_label
            ).exists()
        )


class CarryOverEndpointTests(CarryOverSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.hr = User.objects.create_user(
            username="hr@test.luanar",
            email="hr@test.luanar",
            password="testpass123",
            role=User.Role.HR,
        )
        self.url = f"/api/v1/financial-years/{self.closing.id}/carry-over/"

    def test_requires_authentication(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_hr_is_forbidden(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(LeaveCarryOver.objects.exists())

    def test_hr_runs_rollover_and_gets_a_summary(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)
        self.client.force_authenticate(user=self.hr)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["from_financial_year"], self.closing_label)
        self.assertEqual(response.data["to_financial_year"], self.opening_label)
        self.assertFalse(response.data["dry_run"])
        self.assertEqual(response.data["total_days"], "4")
        self.assertEqual(len(response.data["employees"]), 1)
        self.assertEqual(
            LeaveCarryOver.objects.get(employee=self.user).days, Decimal("4")
        )

    def test_hr_dry_run_writes_nothing(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)
        self.client.force_authenticate(user=self.hr)

        response = self.client.post(self.url, {"dry_run": "1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["dry_run"])
        self.assertEqual(response.data["total_days"], "4")
        self.assertFalse(LeaveCarryOver.objects.exists())

    def test_second_run_is_idempotent(self):
        self._application(status=LeaveApplication.Status.REJECTED, days=4)
        self.client.force_authenticate(user=self.hr)

        self.client.post(self.url)
        second = self.client.post(self.url)

        self.assertEqual(LeaveCarryOver.objects.count(), 1)
        self.assertFalse(second.data["employees"][0]["created"])

    def test_no_following_year_is_a_conflict(self):
        self.opening.delete()
        self.client.force_authenticate(user=self.hr)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(LeaveCarryOver.objects.exists())
