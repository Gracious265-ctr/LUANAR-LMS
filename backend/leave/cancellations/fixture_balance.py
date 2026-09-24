"""Fixture-backed balance provider (Unit 18, section 3.3).

Uses the leave application's leave type to determine whether it deducts annual
leave, and records restorations in the ledger-backed ``LeaveBalanceTransaction``.
``get_deduction`` never touches the ledger (a deduction row may not exist yet for
approved leave seeded before this unit); it derives the amount from the leave
type rules and the application's working days (``calculated_days`` as a
fallback). ``record_restoration`` is idempotent thanks to the partial unique
constraint on ``(cancellation_request, type)`` where ``type = restoration``.
"""

from decimal import Decimal

from django.utils import timezone

from ..models import (
    LeaveApplication,
    LeaveBalanceTransaction,
    LeaveType,
)
from ..providers import get_provider
from .balance import BalanceProvider, DeductionInfo

GENERATED_LEAVE_TYPE_NAMES = {
    1: "Annual Leave",
    2: "Maternity Leave",
    3: "Paternity Leave",
    4: "Compassionate Leave",
}


class FixtureBalanceProvider(BalanceProvider):
    """Read the leave type rules to find deductions and record restorations."""

    def get_deduction(self, application: LeaveApplication) -> DeductionInfo | None:
        """Return the deduction info if the leave type deducts annual leave.

        A ledger ``deduction`` row is authoritative when one exists (the
        section 3.10 fixtures seed one); otherwise the amount is derived from
        the leave type rules and the application's calculated days so approved
        leave seeded before this unit still reports a sensible estimate.
        """
        leave_type_id = application.leave_type_id
        if leave_type_id is None:
            return None

        ledger_row = LeaveBalanceTransaction.objects.filter(
            application=application,
            type=LeaveBalanceTransaction.Type.DEDUCTION,
        ).first()
        if ledger_row is not None:
            return DeductionInfo(
                days=ledger_row.days,
                financial_year=ledger_row.financial_year,
                leave_type_id=ledger_row.leave_type_id,
            )

        provider = get_provider()
        today = timezone.localdate()
        rules = provider.get_leave_type_rules(
            leave_type_id, application.start_date or today
        )
        if rules is None or not rules.deducts_annual_balance:
            return None

        financial_year = application.financial_year_label
        if not financial_year:
            fiscal = provider.get_financial_year_for(application.start_date or today)
            financial_year = fiscal.label if fiscal else ""
        if not financial_year:
            return None

        days = application.working_days or application.calculated_days or 0
        return DeductionInfo(
            days=Decimal(str(days)),
            financial_year=financial_year,
            leave_type_id=leave_type_id,
        )

    def get_ledger_deduction(
        self, application: LeaveApplication
    ) -> DeductionInfo | None:
        """Return the recorded ledger deduction, or None when none exists.

        Final approval calls this (never ``get_deduction``) so a restoration
        entry is only written when days were actually debited from the
        ledger, keeping ``Σ deductions − Σ restorations`` consistent (rule
        2.1.8/9).
        """
        ledger_row = LeaveBalanceTransaction.objects.filter(
            application=application,
            type=LeaveBalanceTransaction.Type.DEDUCTION,
        ).first()
        if ledger_row is None:
            return None
        return DeductionInfo(
            days=ledger_row.days,
            financial_year=ledger_row.financial_year,
            leave_type_id=ledger_row.leave_type_id,
        )

    def record_restoration(
        self,
        application: LeaveApplication,
        cancellation_request,
        days: Decimal,
        financial_year: str,
    ) -> LeaveBalanceTransaction:
        """Record an idempotent balance restoration."""
        existing = LeaveBalanceTransaction.objects.filter(
            cancellation_request=cancellation_request,
            type=LeaveBalanceTransaction.Type.RESTORATION,
        ).first()
        if existing is not None:
            return existing

        return LeaveBalanceTransaction.objects.create(
            employee=application.employee,
            financial_year=financial_year,
            leave_type=_resolve_leave_type(application),
            application=application,
            cancellation_request=cancellation_request,
            type=LeaveBalanceTransaction.Type.RESTORATION,
            days=days,
            carry_forward_eligible=False,
        )


def _resolve_leave_type(application: LeaveApplication) -> LeaveType:
    """Resolve the ledger's non-null ``leave_type`` FK for an application.

    ``LeaveApplication.leave_type_id`` is a soft integer reference; the registry
    (``LeaveType``) is the real target. Look the id up first, then fall back to a
    name-based ``get_or_create`` for the seeded fixture ids so the ledger row is
    never lost to a missing registry entry.
    """
    if application.leave_type_id is not None:
        leave_type = LeaveType.objects.filter(
            pk=application.leave_type_id
        ).first()
        if leave_type is not None:
            return leave_type
    name = GENERATED_LEAVE_TYPE_NAMES.get(application.leave_type_id, "Leave")
    leave_type, _ = LeaveType.objects.get_or_create(
        name=name, defaults={"code": name.lower().replace(" ", "-")}
    )
    return leave_type