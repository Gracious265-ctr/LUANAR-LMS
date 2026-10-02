"""Database-backed implementation of the rules-provider interface (Unit 20).

Replaces the placeholder :class:`~leave.providers.fixture.FixtureRulesProvider`
as the default ``LEAVE_RULES_PROVIDER``. Every method resolves from the real
HR-track tables (Units 2-5); absent configuration returns ``None``/``{}``/``0``
rather than invented data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from users.models import EmployeeProfile

from ..models import LeaveType
from ..services import (
    financial_year_for_date,
    financial_year_label,
    public_holidays_between,
    resolve_leave_rule,
    resolved_annual_entitlement,
)
from .base import (
    DurationUnit,
    EligibilityRule,
    EmployeeInfo,
    FinancialYear,
    LeaveTypeRules,
)

ANNUAL_CODE = "annual"


def _unit_for_code(code: str) -> DurationUnit:
    """LeaveRule stores day counts without units (Unit 20 decision D4).

    Annual leave is measured in working days; every other type in calendar
    days. Documented in ``docs/leave-rules-provider-contract.md``.
    """
    return "working_days" if code == ANNUAL_CODE else "calendar_days"


def _ledger_net(employee_id: int, financial_year_label: str) -> Decimal:
    """Restorations minus deductions from the append-only balance ledger.

    ``deduction`` rows land when an approved application consumes annual leave;
    restorations are written by final cancellations. Absent rows contribute
    zero, so the entitlement answer stands alone.
    """
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
    restored = delta["restoration"] or Decimal(0)
    deducted = delta["deduction"] or Decimal(0)
    return Decimal(restored) - Decimal(deducted)


class DatabaseRulesProvider:
    """Read-only provider backed by the HR-track tables (Units 2-5)."""

    def get_employee_for_user(self, user) -> EmployeeInfo | None:
        profile = getattr(user, "employee_profile", None)
        if profile is None:
            return None

        grade = (profile.grade or "").strip().upper()
        if not grade or not profile.appointment_date:
            return None

        return EmployeeInfo(
            id=user.id,
            user_id=user.id,
            grade=grade,
            appointment_date=profile.appointment_date,
            category=profile.category or None,
            department_id=None,
            gender=(profile.gender or "") or None,
        )

    def get_leave_type_rules(self, leave_type_id: int, as_of: date):
        try:
            leave_type = LeaveType.objects.get(pk=leave_type_id)
        except LeaveType.DoesNotExist:
            return None

        rule = resolve_leave_rule(leave_type, as_of)
        if rule is None:
            return None

        unit = _unit_for_code(leave_type.code)
        eligibility = tuple(
            EligibilityRule(type=item["type"], params=dict(item.get("params") or {}))
            for item in (rule.eligibility_rules or [])
            if isinstance(item, dict) and item.get("type")
        )

        return LeaveTypeRules(
            id=leave_type.id,
            code=leave_type.code,
            name=leave_type.name,
            is_active=True,
            deducts_annual_balance=rule.consumes_annual_entitlement,
            max_duration=rule.max_duration_days,
            max_duration_unit=unit,
            min_notice=rule.min_notice_days,
            min_notice_unit=unit,
            requires_document=rule.requires_supporting_document,
            eligibility=eligibility,
            effective_from=rule.effective_from,
        )

    def get_financial_year_for(self, d: date):
        year = financial_year_for_date(d)
        if year is None:
            return None
        return FinancialYear(
            label=financial_year_label(year),
            start=year.start_date,
            end=year.end_date,
        )

    def get_public_holidays(self, start: date, end: date) -> dict[date, str]:
        return {holiday.date: holiday.name for holiday in public_holidays_between(start, end)}

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        try:
            profile = EmployeeProfile.objects.get(user_id=employee_id)
        except EmployeeProfile.DoesNotExist:
            return Decimal(0)

        entitlement = resolved_annual_entitlement(profile.grade)
        days = entitlement.days if entitlement is not None else 0
        net = Decimal(days) + _ledger_net(employee_id, financial_year_label)
        return max(net, Decimal(0))