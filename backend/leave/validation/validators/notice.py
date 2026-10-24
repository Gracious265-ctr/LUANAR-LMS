"""Notice-period rule.

Code: MIN_NOTICE_NOT_MET.

The notice a leave type requires carries a unit (D2): calendar days or working
days. Working-day notice counts the working days between today and the intended
start, inclusive of the start day (a Monday start after five working days of
notice, from a Monday, is the earliest valid start).
"""

from datetime import date, timedelta

from ..types import ValidationContext, ValidationIssue
from ..working_days import (
    configured_weekdays,
    count_working_days,
    working_days_elapsed,
)


def _earliest_start(
    today: date,
    min_notice: int,
    unit: str,
    holidays: set[date],
    weekdays: set[int],
) -> date:
    """Return the earliest start date that satisfies the notice rule."""
    if unit == "calendar_days":
        earliest = today + timedelta(days=min_notice)
        return earliest if earliest > today else today + timedelta(days=1)

    # Working days: step forward from tomorrow until the notice is met.
    candidate = date.fromordinal(today.toordinal() + 1)
    while count_working_days(
        date.fromordinal(today.toordinal() + 1), candidate, holidays, weekdays
    ) < min_notice:
        candidate = date.fromordinal(candidate.toordinal() + 1)
    return candidate


def validate_notice(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the notice-period rule."""
    rules = ctx.leave_type
    if rules is None or rules.min_notice <= 0:
        return [], []
    if ctx.start_date is None or ctx.today is None:
        return [], ["notice"]

    holidays = set(ctx.holidays)
    weekdays = configured_weekdays()
    unit = rules.min_notice_unit
    if unit == "calendar_days":
        given = (ctx.start_date - ctx.today).days
    elif unit == "working_days":
        given = working_days_elapsed(ctx.today, ctx.start_date, holidays, weekdays)
    else:
        return [], ["notice"]

    if given >= rules.min_notice:
        return [], []

    earliest = _earliest_start(
        ctx.today, rules.min_notice, unit, holidays, weekdays
    )
    unit_label = "working days" if unit == "working_days" else "calendar days"
    message = (
        f"This leave type needs {rules.min_notice} {unit_label} notice. "
        f"The earliest start date is {earliest.strftime('%d %b %Y')}."
    )
    return [
        ValidationIssue(
            code="MIN_NOTICE_NOT_MET",
            field="start_date",
            message=message,
            detail={
                "required": rules.min_notice,
                "given": given,
                "unit": unit,
                "earliest_start": earliest.isoformat(),
            },
        )
    ], []