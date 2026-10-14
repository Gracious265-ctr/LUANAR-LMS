"""Database-backed implementation of the rules-provider interface (Unit 20).

<<<<<<< HEAD
Replaces the placeholder :class:`FixtureRulesProvider`: every method is backed
by the HR-track models (Units 2-5) plus the entitlement/day ledger, so
validation and submission run against the real configuration an HR officer
manages. The swap is one settings change (``LEAVE_RULES_PROVIDER``); nothing
else in ``leave/`` imports the real models directly (decision D1). See
``docs/leave-rules-provider-contract.md`` for the full mapping.

Durability notes (documented in ``context/architecture.md``):

- ``LeaveRule`` stores a single ``max_duration_days`` and ``min_notice_days``
  without a unit. The provider fixes ``max_duration_unit="calendar_days"`` and
  ``min_notice_unit="working_days"``: capped durations (maternity 90, paternity
  10, compassionate 5) are calendar-day limits and notice is counted in working
  days, matching LUANAR policy.
- ``LeaveType`` has no active/inactive flag, so ``is_active`` is always
  ``True``.
- Structured eligibility is read from ``LeaveRule.eligibility_rules`` (JSON,
  D7 vocabulary: gender/min_service/grade_range/employee_category). The free
  text ``eligibility`` field remains the HR-authored description for display.
- ``EmployeeInfo.department_id`` stays ``None`` because ``EmployeeProfile``
  stores department as free text, not a department reference.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from ..services import (
    financial_year_for_date,
    resolve_grade_entitlement,
    resolve_leave_rule,
)
from .base import (
    EmployeeInfo,
    EligibilityRule,
    FinancialYear,
    LeaveBalance,
    LeaveBalanceUnavailableError,
    LeaveTypeRules,
)


def _ledger_net_used(employee_id: int, financial_year_label: str) -> Decimal:
    """Net days deducted in ``financial_year_label`` (ledger section).

    Computed from the append-only ledger as sum(deductions) - sum(restorations)
    for the employee and financial year. Returns 0 when no ledger rows exist.
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


def _financial_year_label(start: date, end: date) -> str:
    """Label in the app's ``LV-YYYY-YY`` convention, e.g. ``2026-27``."""
    return f"{start.year}-{end.year % 100:02d}"


class DatabaseRulesProvider:
    """Read-only provider backed by the HR-track models and the ledger."""
=======
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


def _plan_reservation_net(employee_id: int, financial_year_label: str) -> Decimal:
    """Reserved capacity minus released capacity from the plan ledger.

    An approved leave day plan reserves its annual-deducting blocks' working
    days up front, so those days are already spoken for when somebody applies
    for the same leave later. Explicit releases (the employee declining, HR
    releasing, or the block auto-lapsing at its start date) return them.
    ``confirm`` rows never touch capacity because the ``reserve`` row already
    held the days.

    Imported lazily: the plans app depends on this provider for validation, so a
    module-level import would be circular.
    """
    from django.db.models import Q, Sum

    from plans.models import PlanBalanceTransaction

    delta = PlanBalanceTransaction.objects.filter(
        employee_id=employee_id,
        financial_year=financial_year_label,
    ).aggregate(
        reserved=Sum(
            "days",
            filter=Q(type=PlanBalanceTransaction.Type.RESERVE),
        ),
        released=Sum(
            "days",
            filter=Q(type=PlanBalanceTransaction.Type.RELEASE),
        ),
    )
    reserved = delta["reserved"] or Decimal(0)
    released = delta["released"] or Decimal(0)
    return Decimal(reserved) - Decimal(released)


class DatabaseRulesProvider:
    """Read-only provider backed by the HR-track tables (Units 2-5)."""
>>>>>>> feature/plans-teams

    def get_employee_for_user(self, user) -> EmployeeInfo | None:
        profile = getattr(user, "employee_profile", None)
        if profile is None:
            return None
<<<<<<< HEAD
        grade = profile.grade.strip().upper() if profile.grade else ""
        if not grade or profile.appointment_date is None:
            return None
        gender = profile.gender.strip().upper() if profile.gender else None
=======

        grade = (profile.grade or "").strip().upper()
        if not grade:
            return None

>>>>>>> feature/plans-teams
        return EmployeeInfo(
            id=user.id,
            user_id=user.id,
            grade=grade,
            appointment_date=profile.appointment_date,
            category=profile.category or None,
<<<<<<< HEAD
            department_id=None,
            gender=gender,
        )

    def get_leave_type_rules(self, leave_type_id: int, as_of: date):
        from leave.models import LeaveType

        leave_type = LeaveType.objects.filter(pk=leave_type_id).first()
        if leave_type is None:
            return None
        rule = resolve_leave_rule(leave_type, as_of)
        if rule is None:
            return None
        return LeaveTypeRules(
            id=leave_type.pk,
=======
            team_id=None,
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
>>>>>>> feature/plans-teams
            code=leave_type.code,
            name=leave_type.name,
            is_active=True,
            deducts_annual_balance=rule.consumes_annual_entitlement,
            max_duration=rule.max_duration_days,
<<<<<<< HEAD
            max_duration_unit="calendar_days",
            min_notice=rule.min_notice_days,
            min_notice_unit="working_days",
            requires_document=rule.requires_supporting_document,
            eligibility=tuple(
                EligibilityRule(
                    str(item.get("type", "")),
                    dict(item.get("params") or {}),
                )
                for item in (rule.eligibility_rules or [])
            ),
=======
            max_duration_unit=unit,
            min_notice=rule.min_notice_days,
            min_notice_unit=unit,
            requires_document=rule.requires_supporting_document,
            eligibility=eligibility,
>>>>>>> feature/plans-teams
            effective_from=rule.effective_from,
        )

    def get_financial_year_for(self, d: date):
        year = financial_year_for_date(d)
        if year is None:
            return None
        return FinancialYear(
<<<<<<< HEAD
            label=_financial_year_label(year.start_date, year.end_date),
=======
            label=financial_year_label(year),
>>>>>>> feature/plans-teams
            start=year.start_date,
            end=year.end_date,
        )

    def get_public_holidays(self, start: date, end: date) -> dict[date, str]:
<<<<<<< HEAD
        from leave.models import PublicHoliday

        return {
            holiday.date: holiday.name
            for holiday in PublicHoliday.objects.filter(
                date__gte=start, date__lte=end
            ).order_by("date")
        }

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        return Decimal(self._entitlement_days(employee_id)) - _ledger_net_used(
            employee_id, financial_year_label
        )

    def get_leave_balance(self, employee_id: int, financial_year_label: str):
        if self._grade_for(employee_id) is None:
            raise LeaveBalanceUnavailableError(
                f"No employee record usable to resolve the balance "
                f"for employee {employee_id}."
            )
        entitlement = self._entitlement_days(employee_id)
        net_used = _ledger_net_used(employee_id, financial_year_label)
        return LeaveBalance(
            entitlement=entitlement,
            used=int(net_used),
            available=int(entitlement) - int(net_used),
        )

    def _grade_for(self, employee_id: int) -> str | None:
        from users.models import User

        user = User.objects.filter(id=employee_id).first()
        if user is None:
            return None
        profile = getattr(user, "employee_profile", None)
        if profile is None or not profile.grade:
            return None
        return profile.grade.strip().upper()

    def _entitlement_days(self, employee_id: int) -> int:
        grade = self._grade_for(employee_id)
        if grade is None:
            return 0
        rule = resolve_grade_entitlement(grade, timezone.localdate())
        return rule.days if rule is not None else 0
=======
        return {holiday.date: holiday.name for holiday in public_holidays_between(start, end)}

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        try:
            profile = EmployeeProfile.objects.get(user_id=employee_id)
        except EmployeeProfile.DoesNotExist:
            return Decimal(0)

        entitlement = resolved_annual_entitlement(profile.grade)
        days = entitlement.days if entitlement is not None else 0
        net = (
            Decimal(days)
            + _ledger_net(employee_id, financial_year_label)
            - _plan_reservation_net(employee_id, financial_year_label)
        )
        return max(net, Decimal(0))
>>>>>>> feature/plans-teams
