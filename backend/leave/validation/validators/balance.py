"""Annual-balance rule.

Code: INSUFFICIENT_BALANCE.

Runs only for annual-deducting leave types with a resolved financial year (D4).
The balance is **the approved-deduction balance** asked of the provider via
``get_available_balance``; pending/rejected applications are
deliberately not consulted. This validator never writes anything.
"""

from decimal import Decimal

from ..types import ValidationContext, ValidationIssue


def validate_balance(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the balance rule."""
    rules = ctx.leave_type
    if (
        rules is None
        or not rules.deducts_annual_balance
        or ctx.financial_year is None
        or ctx.working_days is None
    ):
        return [], []

    if ctx.employee is None:
        return [], ["balance"]

    available = provider.get_available_balance(
        ctx.employee.id, ctx.financial_year.label
    )
    ctx.available_balance = available
    ctx.balance_after_if_approved = available - Decimal(ctx.working_days)

    if ctx.working_days <= available:
        return [], []

    return [
        ValidationIssue(
            code="INSUFFICIENT_BALANCE",
            field="end_date",
            message=(
                f"The requested {ctx.working_days} working days exceed your "
                f"available balance of {available} days."
            ),
            detail={
                "available": str(available),
                "requested": ctx.working_days,
            },
        )
    ], []