"""Balance provider (Unit 18, spec 3.3).

The provider answers two questions the cancellation service needs:

* ``get_deduction`` — did the approved application deduct annual leave, and
  how many days / from which financial year? Returns ``None`` for leave types
  that never deduct (maternity, paternity, compassionate, ...).
* ``record_restoration`` — idempotently add the restoration row to the ledger.

The ledger-backed implementation ships here and is swapped for the real
HR-track provider at Unit 20 (reconciliation note in ``docs/``). The day count
is derived from the approved application's snapshot, falling back to the
HR-configured leave type when a snapshot is absent. Nothing here reads a
hard-coded fixture registry: whether a leave type deducts annual leave is
business data HR owns, so an application with neither a snapshot nor a
configured type resolves to "does not deduct" rather than to a placeholder
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils.module_loading import import_string

LUANAR_TZ = ZoneInfo("Africa/Blantyre")


@dataclass(frozen=True)
class DeductionInfo:
    """The annual-leave deduction an approved application accounts for."""

    days: Decimal
    financial_year: str


class BalanceProvider(Protocol):
    def get_deduction(self, application) -> DeductionInfo | None: ...

    def record_restoration(
        self, application, cancellation_request, days: Decimal, financial_year: str
    ): ...


def get_balance_provider() -> BalanceProvider:
    """Instantiate the configured ``LEAVE_BALANCE_PROVIDER``."""
    return import_string(settings.LEAVE_BALANCE_PROVIDER)()


def get_today():
    """Today's date in LUANAR local time (Africa/Blantyre).

    The single "today" seam for Unit 18; injectable at the service borders.
    """
    from django.utils import timezone

    return timezone.localdate()


def _deducts_annual_balance(application) -> bool:
    """Whether the application's leave type deducts annual leave.

    The submission snapshot owns the answer, because it is the configuration
    the application was actually approved under. Only when no snapshot exists —
    a row created directly, outside the normal submission path — does the
    live ``leave_config`` flag answer. With neither, the safe answer is
    "does not deduct": a cancellation must never invent a restoration the
    configuration never granted.
    """
    snapshot = application.rules_snapshot or {}
    leave_type = snapshot.get("leave_type") or {}
    if "deducts_annual_balance" in leave_type:
        return bool(leave_type["deducts_annual_balance"])

    leave_type_id = application.leave_type_id
    if leave_type_id:
        consumes = _consumes_flag(leave_type_id)
        if consumes is not None:
            return consumes

    return False


def _consumes_flag(leave_type_id: int) -> bool | None:
    """The type's live ``consumes_annual_entitlement``, or None if it is gone."""
    from leave_config.services import consumes_annual_entitlement

    try:
        return consumes_annual_entitlement(leave_type_id)
    except Exception:  # pragma: no cover - unknown type or a migration race
        return None


class LedgerBalanceProvider:
    """Ledger-backed balance provider (``LeaveBalanceTransaction``)."""

    def get_deduction(self, application) -> DeductionInfo | None:
        if not _deducts_annual_balance(application):
            return None
        days = application.working_days
        financial_year = application.financial_year_label
        if not days or days <= 0 or not financial_year:
            return None
        return DeductionInfo(days=Decimal(days), financial_year=financial_year)

    def record_restoration(
        self, application, cancellation_request, days: Decimal, financial_year: str
    ):
        from .models import LeaveBalanceTransaction

        return LeaveBalanceTransaction.objects.get_or_create(
            cancellation_request=cancellation_request,
            type=LeaveBalanceTransaction.Type.RESTORATION,
            defaults={
                "employee_id": application.employee_id,
                "financial_year": financial_year,
                "leave_type": application.leave_type_id,
                "application": application,
                "days": days,
                "carry_forward_eligible": False,
            },
        )[0]