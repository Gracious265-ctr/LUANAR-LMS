"""Precondition checks for the validation pipeline.

Codes: EMPLOYEE_PROFILE_MISSING, LEAVE_TYPE_UNAVAILABLE, END_BEFORE_START.

If any precondition fails, nothing else can be evaluated, so the runner stops
after these to avoid cascading nonsense errors.
"""

from ..types import ValidationContext, ValidationIssue


def validate_preconditions(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], bool]:
    """Return ``(issues, can_continue)``.

    ``can_continue`` is True only when no precondition failure was recorded.
    """
    issues: list[ValidationIssue] = []

    if ctx.employee is None:
        issues.append(
            ValidationIssue(
                code="EMPLOYEE_PROFILE_MISSING",
                field="—",
                message=(
                    "We could not find your employee profile. "
                    "Contact HR before applying for leave."
                ),
            )
        )

    if ctx.leave_type is None:
        issues.append(
            ValidationIssue(
                code="LEAVE_TYPE_UNAVAILABLE",
                field="leave_type",
                message=(
                    "This leave type is not available for applications "
                    "on the submission date."
                ),
            )
        )

    start, end = ctx.start_date, ctx.end_date
    if start is None or end is None:
        field = "end_date" if start is not None else "start_date"
        issues.append(
            ValidationIssue(
                code="END_BEFORE_START",
                field=field,
                message="A valid start and end date are required.",
                detail={"start_date": start.isoformat() if start else None,
                        "end_date": end.isoformat() if end else None},
            )
        )
    elif end < start:
        issues.append(
            ValidationIssue(
                code="END_BEFORE_START",
                field="end_date",
                message="The end date must not be before the start date.",
                detail={"start_date": start.isoformat(), "end_date": end.isoformat()},
            )
        )

    return issues, not issues