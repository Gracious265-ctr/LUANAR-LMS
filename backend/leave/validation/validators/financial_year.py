"""Financial-year containment.

Codes: NO_FINANCIAL_YEAR_CONFIGURED, CROSSES_FINANCIAL_YEAR.

The leave range must sit inside a single configured financial year; the year
containing the start date is stored on the context for the balance check and
the reference number (D8).
"""

from ..types import ValidationContext, ValidationIssue


def validate_financial_year(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the financial-year rules."""
    if ctx.start_date is None or ctx.end_date is None:
        return [], ["financial_year"]

    issues: list[ValidationIssue] = []
    start, end = ctx.start_date, ctx.end_date

    start_fy = provider.get_financial_year_for(start)
    end_fy = provider.get_financial_year_for(end)

    if start_fy is None:
        issues.append(
            ValidationIssue(
                code="NO_FINANCIAL_YEAR_CONFIGURED",
                field="start_date",
                message="The start date is not inside any configured financial year.",
                detail={"start_date": start.isoformat()},
            )
        )
    if end_fy is None:
        issues.append(
            ValidationIssue(
                code="NO_FINANCIAL_YEAR_CONFIGURED",
                field="end_date",
                message="The end date is not inside any configured financial year.",
                detail={"end_date": end.isoformat()},
            )
        )

    ctx.financial_year = start_fy

    if (
        start_fy is not None
        and end_fy is not None
        and start_fy.label != end_fy.label
    ):
        issues.append(
            ValidationIssue(
                code="CROSSES_FINANCIAL_YEAR",
                field="end_date",
                message=(
                    f"This leave spans two financial years ({start_fy.label} "
                    f"and {end_fy.label}); it must fit inside one."
                ),
                detail={
                    "start_year": start_fy.label,
                    "end_year": end_fy.label,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                },
            )
        )

    return issues, []