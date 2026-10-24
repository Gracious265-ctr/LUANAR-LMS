"""Database-backed implementation of the rules-provider interface (Unit 20).

Replaces the placeholder :class:`~leave.providers.fixture.FixtureRulesProvider`
as the default ``LEAVE_RULES_PROVIDER``. Every method resolves from the real
HR-track tables (Units 2-5); absent configuration returns ``None``/``{}``/``0``
rather than invented data.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from leave_types.models import LeaveType
from leave_types.services import day_unit_for
from users.models import EmployeeProfile

from calendar_app.services import holidays_map

from ..services import (
    financial_year_for_date,
    financial_year_label,
    resolved_annual_entitlement,
)
from .base import (
    EligibilityRule,
    EmployeeInfo,
    FinancialYear,
    LeaveTypeRules,
)


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


def _carry_over_days(employee_id: int, financial_year_label: str) -> Decimal:
    """Days carried *into* the given financial year from the previous one.

    Rejected-leave carry-over only (see ``leave.services.carry_over``): rows
    written at rollover name this year as ``to_financial_year``. Absent rows
    contribute zero, so a year with no rollover is unchanged.
    """
    from ..services.carry_over import carry_over_days_for_year

    return carry_over_days_for_year(employee_id, financial_year_label)


class DatabaseRulesProvider:
    """Read-only provider backed by the HR-track tables (Units 2-5)."""

    def get_employee_for_user(self, user) -> EmployeeInfo | None:
        profile = getattr(user, "employee_profile", None)
        if profile is None:
            return None

        grade = (profile.grade or "").strip().upper()
        if not grade:
            return None

        return EmployeeInfo(
            id=user.id,
            user_id=user.id,
            grade=grade,
            appointment_date=profile.appointment_date,
            category=profile.category or None,
            team_id=None,
            gender=(profile.gender or "") or None,
        )

    def get_leave_type_rules(self, leave_type_id: int, as_of: date):
        """The type's live policy.

        The type *is* the rule since refinement unit 06 retired effective-dated
        ``LeaveRule`` rows, so ``as_of`` no longer narrows the answer: it stays
        in the protocol signature because the fixture provider and the snapshot
        shape both carry it. A missing type still returns ``None``.
        """
        try:
            leave_type = LeaveType.objects.get(pk=leave_type_id)
        except LeaveType.DoesNotExist:
            return None

        unit = day_unit_for(leave_type)
        eligibility = tuple(
            EligibilityRule(type=item["type"], params=dict(item.get("params") or {}))
            for item in (leave_type.eligibility_rules or [])
            if isinstance(item, dict) and item.get("type")
        )

        return LeaveTypeRules(
            id=leave_type.id,
            code=leave_type.code,
            name=leave_type.name,
            is_active=leave_type.is_active,
            deducts_annual_balance=leave_type.consumes_annual_entitlement,
            max_duration=leave_type.max_duration_days,
            max_duration_unit=unit,
            min_notice=leave_type.notice_days or 0,
            min_notice_unit=unit,
            requires_document=leave_type.requires_supporting_document,
            eligibility=eligibility,
            effective_from=leave_type.created_at.date(),
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
        return holidays_map(start, end)

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        try:
            profile = EmployeeProfile.objects.get(user_id=employee_id)
        except EmployeeProfile.DoesNotExist:
            return Decimal(0)

        entitlement = resolved_annual_entitlement(profile.grade)
        days = entitlement.days if entitlement is not None else 0
        net = (
            Decimal(days)
            + _carry_over_days(employee_id, financial_year_label)
            + _ledger_net(employee_id, financial_year_label)
        )
        return max(net, Decimal(0))