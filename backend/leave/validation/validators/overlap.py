"""Overlap rule.

Code: OVERLAPPING_LEAVE.

An application must not overlap another application of the same employee whose
status is in ``settings.LEAVE_BLOCKING_STATUSES`` (D3: submitted, pending,
correction_required, approved). Overlap is calendar-date based, across all
leave types, and an application never overlaps itself. Drafts, rejected and
cancelled applications do not block.
"""

from django.conf import settings

from ..types import ValidationContext, ValidationIssue


def validate_overlap(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the overlap rule."""
    if ctx.start_date is None or ctx.end_date is None:
        return [], ["overlap"]

    from ...models import LeaveApplication  # own unit's model

    queryset = LeaveApplication.objects.filter(
        employee=ctx.user,
        status__in=settings.LEAVE_BLOCKING_STATUSES,
        start_date__lte=ctx.end_date,
        end_date__gte=ctx.start_date,
        start_date__isnull=False,
        end_date__isnull=False,
    )
    if ctx.application is not None:
        queryset = queryset.exclude(id=ctx.application.id)

    blocking = list(queryset.order_by("start_date"))
    if not blocking:
        return [], []

    references = [app.reference_number for app in blocking if app.reference_number]
    labels = [app.reference_number or app.start_date.isoformat() for app in blocking]
    return [
        ValidationIssue(
            code="OVERLAPPING_LEAVE",
            field="start_date",
            message=(
                "This leave overlaps an existing application"
                + ("s" if len(labels) > 1 else "")
                + f" ({', '.join(labels)})."
            ),
            detail={"references": references},
        )
    ], []