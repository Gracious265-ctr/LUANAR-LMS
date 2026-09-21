"""Reason-required rule.

Code: REASON_REQUIRED.

Runs only when a draft/application is attached. A blank or whitespace-only
reason blocks submission (D13); the project overview requires a reason on every
application.
"""

from ..types import ValidationContext, ValidationIssue


def _reason_is_blank(application) -> bool:
    return not (application.reason or "").strip()


def validate_reason(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the reason requirement."""
    if ctx.application is None:
        return [], ["reason"]
    if not _reason_is_blank(ctx.application):
        return [], []

    return [
        ValidationIssue(
            code="REASON_REQUIRED",
            field="reason",
            message="Please provide a reason for your leave application.",
        )
    ], []