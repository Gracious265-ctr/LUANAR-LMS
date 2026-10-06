"""In-memory, fixture-backed implementation of the rules-provider interface.

This is the placeholder provider for Unit 14 (decision D1): validation and
submission run against its data until the HR-track models are merged. See
``docs/leave-rules-provider-contract.md`` for the real-model mapping.
"""

from datetime import date
from decimal import Decimal

from . import fixture_data as data
from .base import EmployeeInfo


def _entitlement_days(grade: str) -> int:
    days = data.annual_entitlement_for_grade(grade)
    return days if days is not None else 0


class FixtureRulesProvider:
    """Read-only provider backed by ``fixture_data`` placeholder values."""

    def __init__(self) -> None:
        self._grades: dict[int, str] = {}

    def get_employee_for_user(self, user) -> EmployeeInfo | None:
        username = user.username
        row = data.EMPLOYEES.get(username)
        profile = getattr(user, "employee_profile", None)
        if row is None and profile is None:
            return None

        grade = ""
        if profile is not None and profile.grade:
            grade = profile.grade.strip().upper()
        if not grade and row:
            grade = row["grade"]

        appointment = None
        if profile is not None:
            appointment = profile.appointment_date
        if appointment is None and row:
            appointment = row["appointment_date"]

        if not grade:
            return None

        category = None
        if profile is not None and profile.category:
            category = profile.category
        elif row:
            category = row.get("category")
        gender = row.get("gender") if row else None

        self._grades[user.id] = grade
        return EmployeeInfo(
            id=user.id,
            user_id=user.id,
            grade=grade,
            appointment_date=appointment,
            category=category,
            department_id=None,
            gender=gender,
        )

    def get_leave_type_rules(self, leave_type_id: int, as_of: date):
        for rules in data.LEAVE_TYPES:
            if rules.id != leave_type_id:
                continue
            if not rules.is_active or rules.effective_from > as_of:
                return None
            return rules
        return None

    def get_financial_year_for(self, d: date):
        for year in data.FINANCIAL_YEARS:
            if year.start <= d <= year.end:
                return year
        return None

    def get_public_holidays(self, start: date, end: date) -> dict[date, str]:
        return {
            day: name
            for day, name in data.PUBLIC_HOLIDAYS.items()
            if start <= day <= end
        }

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        grade = self._grades.get(employee_id, "")
        net = Decimal(_entitlement_days(grade)) + _ledger_net(
            employee_id, financial_year_label
        )
        return max(net, Decimal(0))


def _ledger_net(employee_id: int, financial_year_label: str) -> Decimal:
    """Restorations minus deductions from the append-only balance ledger.

    Lazy import keeps the provider free of circular imports. ``deduction`` rows
    land when an approved application consumes annual leave; restorations are
    written only by Unit 18 final cancellations. Absent rows contribute zero, so
    the placeholder entitlement answer is unchanged for existing scenarios.
    """
    try:
        from django.db.models import Q, Sum

        from leave.cancellations.models import LeaveBalanceTransaction

        delta = LeaveBalanceTransaction.objects.filter(
            employee_id=employee_id,
            financial_year=financial_year_label,
        ).aggregate(
            restoration=Sum(
                "days",
                filter=Q(type=LeaveBalanceTransaction.Type.RESTORATION),
            ),
            deduction=Sum(
                "days",
                filter=Q(type=LeaveBalanceTransaction.Type.DEDUCTION),
            ),
        )
    except Exception:  # pragma: no cover - race with migration state
        return Decimal(0)
    restored = delta["restoration"] or Decimal(0)
    deducted = delta["deduction"] or Decimal(0)
    return Decimal(restored) - Decimal(deducted)