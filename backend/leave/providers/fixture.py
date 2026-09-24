"""In-memory, fixture-backed implementation of the rules-provider interface.

This is the placeholder provider for Unit 14 (decision D1): validation and
submission run against its data until the HR-track models are merged. See
``docs/leave-rules-provider-contract.md`` for the real-model mapping.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from . import fixture_data as data
from .base import EmployeeInfo, LeaveBalance


def _ledger_net_used(employee_id: int, financial_year_label: str) -> Decimal:
    """Net days deducted in ``financial_year_label`` (section 3.3).

    Computed from the append-only ledger as sum(deductions) - sum(restorations)
    for the employee and financial year. Returns 0 when no ledger rows exist,
    which keep the legacy caller behaviour for untouched databases.
    """
    from leave.models import LeaveBalanceTransaction

    row = (
        LeaveBalanceTransaction.objects.filter(
            employee_id=employee_id,
            financial_year=financial_year_label,
        )
        .aggregate(
            deducted=Sum(
                "days",
                filter=Q(type=LeaveBalanceTransaction.Type.DEDUCTION),
            ),
            restored=Sum(
                "days",
                filter=Q(type=LeaveBalanceTransaction.Type.RESTORATION),
            ),
        )
    )
    deducted = row["deducted"] or Decimal("0")
    restored = row["restored"] or Decimal("0")
    return deducted - restored


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

        if not grade or not appointment:
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
        grade = self._grade_for(employee_id)
        net_used = _ledger_net_used(employee_id, financial_year_label)
        return Decimal(_entitlement_days(grade)) - net_used

    def get_leave_balance(self, employee_id: int, financial_year_label: str):
        grade = self._grade_for(employee_id)
        entitlement = Decimal(_entitlement_days(grade))
        net_used = _ledger_net_used(employee_id, financial_year_label)
        return LeaveBalance(
            entitlement=entitlement,
            used=net_used,
            available=entitlement - net_used,
        )

    def _grade_for(self, employee_id: int) -> str:
        """Resolve an employee's current grade without per-instance caching.

        The approvals detail payload (Unit 16) asks for the live balance of any
        employee, on a fresh provider instance, so it cannot rely on the
        ``_grades`` cache primed by a prior ``get_employee_for_user`` call.
        """
        from users.models import User

        user = User.objects.filter(id=employee_id).first()
        if user is None:
            return ""
        profile = getattr(user, "employee_profile", None)
        if profile is not None and profile.grade:
            return profile.grade.strip().upper()
        row = data.EMPLOYEES.get(user.username)
        return row["grade"] if row else ""