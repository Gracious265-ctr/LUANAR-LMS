"""Start-date rules.

Codes: START_ON_SUBMISSION_DATE, START_IN_PAST, START_NOT_WORKING_DAY,
NO_WORKING_DAYS.

A start date must be a future working day (D5); the working/calendar day counts
for the whole range are computed here and stored on the context for the later
checks and the rules snapshot.
"""

from ..types import ValidationContext, ValidationIssue
from ..working_days import (
    configured_weekdays,
    count_calendar_days,
    count_working_days,
    is_weekend,
)


def validate_start_date(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the start-date rules."""
    if ctx.start_date is None or ctx.end_date is None:
        return [], ["start_date"]

    issues: list[ValidationIssue] = []
    start, end, today = ctx.start_date, ctx.end_date, ctx.today
    weekdays = configured_weekdays()

    if start == today:
        issues.append(
            ValidationIssue(
                code="START_ON_SUBMISSION_DATE",
                field="start_date",
                message="The start date must be a future date, not today.",
                detail={"start_date": start.isoformat()},
            )
        )
    elif start < today:
        issues.append(
            ValidationIssue(
                code="START_IN_PAST",
                field="start_date",
                message="The start date must not be in the past.",
                detail={"start_date": start.isoformat()},
            )
        )
    else:
        holiday_name = ctx.holidays.get(start)
        if is_weekend(start, weekdays):
            issues.append(
                ValidationIssue(
                    code="START_NOT_WORKING_DAY",
                    field="start_date",
                    message=start.strftime("A weekend (%A) cannot be the first day of leave."),
                    detail={"reason": "weekend", "start_date": start.isoformat()},
                )
            )
        elif holiday_name:
            issues.append(
                ValidationIssue(
                    code="START_NOT_WORKING_DAY",
                    field="start_date",
                    message=(
                        f"{holiday_name} is a public holiday and cannot be "
                        "the first day of leave."
                    ),
                    detail={"reason": holiday_name, "start_date": start.isoformat()},
                )
            )

    holidays = set(ctx.holidays)
    ctx.working_days = count_working_days(start, end, holidays, weekdays)
    ctx.calendar_days = count_calendar_days(start, end)

    if ctx.working_days == 0:
        issues.append(
            ValidationIssue(
                code="NO_WORKING_DAYS",
                field="end_date",
                message="This date range contains no working days.",
                detail={
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "working_days": 0,
                },
            )
        )

    return issues, []