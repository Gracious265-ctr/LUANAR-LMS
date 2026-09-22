"""Duration limit rule.

Code: MAX_DURATION_EXCEEDED.

The configured maximum carries a unit (D2): measure the range in
``max_duration_unit`` and fail when it exceeds the maximum.
"""

from ..types import ValidationContext, ValidationIssue


def validate_duration(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the duration limit rule."""
    rules = ctx.leave_type
    if rules is None or rules.max_duration is None:
        return [], []

    if rules.max_duration_unit == "working_days":
        measured = ctx.working_days
    elif rules.max_duration_unit == "calendar_days":
        measured = ctx.calendar_days
    else:
        return [], ["duration"]

    if measured is None:
        return [], ["duration"]

    if measured <= rules.max_duration:
        return [], []

    unit = rules.max_duration_unit
    unit_label = "working days" if unit == "working_days" else "calendar days"
    return [
        ValidationIssue(
            code="MAX_DURATION_EXCEEDED",
            field="end_date",
            message=(
                f"This leave type allows at most {rules.max_duration} "
                f"{unit_label}; the requested range is {measured}."
            ),
            detail={
                "max_duration": rules.max_duration,
                "measured": measured,
                "unit": unit,
            },
        )
    ], []