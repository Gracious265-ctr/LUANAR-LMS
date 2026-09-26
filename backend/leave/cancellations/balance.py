"""Balance provider interface (Unit 18, section 3.3).

Provides deduction lookup and restoration recording for the cancellation
flow. The fixture-backed implementation ships with this unit until Unit 20.
"""

from dataclasses import dataclass
from decimal import Decimal

from ..models import LeaveApplication, LeaveBalanceTransaction, CancellationRequest


@dataclass(frozen=True)
class DeductionInfo:
    """A deduction previously applied to an annual-leave balance."""

    days: Decimal
    financial_year: str
    leave_type_id: int | None = None


class BalanceProvider:
    """Interface for balance operations used by the cancellation flow."""

    def get_deduction(
        self, application: LeaveApplication
    ) -> DeductionInfo | None:
        """Return the deduction applied to this application, or None if
        the leave type does not deduct annual leave."""
        raise NotImplementedError

    def get_ledger_deduction(
        self, application: LeaveApplication
    ) -> DeductionInfo | None:
        """Return the actual recorded ledger deduction, or None when no
        ``deduction`` transaction exists yet.

        Unlike ``get_deduction`` this never falls back to a derived
        estimate: it exists so final approval only restores days that were
        actually debited from the ledger (rule 2.1.8/9)."""
        raise NotImplementedError

    def record_deduction(
        self, application: LeaveApplication
    ) -> LeaveBalanceTransaction | None:
        """Create/return the single DEDUCTION ledger row for an approved
        application.

        Returns ``None`` when the leave type does not deduct annual leave
        (decided from the immutable ``rules_snapshot``, invariant 12.5). The
        row is idempotent: an existing deduction is returned as-is, never
        duplicated and never rewritten, keeping ``Σ deductions − Σ
        restorations`` consistent (rule 2.1.8/9)."""
        raise NotImplementedError

    def record_restoration(
        self,
        application: LeaveApplication,
        cancellation_request: CancellationRequest,
        days: Decimal,
        financial_year: str,
    ) -> LeaveBalanceTransaction:
        """Record an idempotent balance restoration. Returns the
        :class:`LeaveBalanceTransaction` row (new or existing)."""
        raise NotImplementedError