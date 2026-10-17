"""Ordered runner for the leave validation pipeline (Unit 14).

Every run collects **all** errors at once (D11): preconditions run first and
stop the run when any fails; otherwise every independent check runs in order and
a check that cannot be evaluated (a value an earlier failure made unavailable,
or a draft-less run lacking the reason/documents checks) is skipped and listed
in ``skipped_checks`` rather than errored.
"""

from datetime import date, timedelta
from decimal import Decimal

from ..providers import get_provider, get_today
from .types import ValidationResult, ValidationContext, VALIDATOR_VERSION  # noqa: F401
from .validators import (
    balance,
    documents,
    duration,
    eligibility,
    financial_year,
    notice,
    overlap,
    preconditions,
    reason,
    start_date,
)

CHECK_ORDER = [
    "start_date",
    "financial_year",
    "notice",
    "duration",
    "eligibility",
    "documents",
    "reason",
    "overlap",
    "balance",
]

_VALIDATORS = {
    "start_date": start_date.validate_start_date,
    "financial_year": financial_year.validate_financial_year,
    "notice": notice.validate_notice,
    "duration": duration.validate_duration,
    "eligibility": eligibility.validate_eligibility,
    "documents": documents.validate_documents,
    "reason": reason.validate_reason,
    "overlap": overlap.validate_overlap,
    "balance": balance.validate_balance,
}


def run_validation(
    *,
    user,
    leave_type_id: int,
    start_date_raw,
    end_date_raw,
    application=None,
    today: date | None = None,
    as_of: date | None = None,
    exclude_application_id=None,
) -> ValidationResult:
    """Run the full validation pipeline and return a :class:`ValidationResult`.

    ``as_of``/``today`` name the same clock seam (``as_of`` is preferred);
    ``exclude_application_id`` lets a resubmission validate the employee's
    other open applications without treating the live application (or its draft)
    as its own overlap blocker.
    """
    today = today or as_of or get_today()
    provider = get_provider()

    employee = provider.get_employee_for_user(user)
    leave_type = provider.get_leave_type_rules(leave_type_id, today) if leave_type_id else None

    ctx = ValidationContext(
        user=user,
        employee=employee,
        leave_type=leave_type,
        start_date=start_date_raw,
        end_date=end_date_raw,
        application=application,
        today=today,
        exclude_application_id=exclude_application_id,
    )

    errors, skipped = [], []
    pre_issues, can_continue = preconditions.validate_preconditions(ctx, provider)
    errors += pre_issues

    if can_continue:
        holiday_start = min(today + timedelta(days=1), ctx.start_date)
        ctx.holidays = provider.get_public_holidays(holiday_start, ctx.end_date)

        for name in CHECK_ORDER:
            new_issues, new_skipped = _VALIDATORS[name](ctx, provider)
            errors += new_issues
            skipped += new_skipped

    return _build_result(ctx, errors, skipped)


def _build_result(ctx: ValidationContext, errors, skipped) -> ValidationResult:
    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=[],
        skipped_checks=skipped,
        working_days=ctx.working_days,
        calendar_days=ctx.calendar_days,
        financial_year=ctx.financial_year.label if ctx.financial_year else None,
        available_balance=ctx.available_balance,
        balance_after_if_approved=ctx.balance_after_if_approved,
        context=ctx,
    )