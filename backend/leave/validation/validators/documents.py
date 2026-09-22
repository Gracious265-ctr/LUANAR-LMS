"""Required-document rule.

Code: DOCUMENT_REQUIRED.

Runs only when a draft/application is attached (no draft: the check is skipped,
not failed). "Required document" (D12) means the leave type has
``requires_document`` and no finalized supporting document exists on the draft.
"""

from ..types import ValidationContext, ValidationIssue


def count_supporting_documents(application) -> int:
    """Return the number of documents on an application.

    Thin wrapper over the Unit 13 ``SupportingDocument`` relation so a model
    or manager rename touches exactly one function.
    """
    return application.documents.count()


def validate_documents(
    ctx: ValidationContext, provider
) -> tuple[list[ValidationIssue], list[str]]:
    """Return ``(issues, skipped)`` for the required-document rule."""
    if ctx.application is None:
        return [], ["documents"]

    rules = ctx.leave_type
    if rules is None:
        return [], []
    if not rules.requires_document:
        return [], []
    if count_supporting_documents(ctx.application) > 0:
        return [], []

    return [
        ValidationIssue(
            code="DOCUMENT_REQUIRED",
            field="documents",
            message=(
                "This leave type requires at least one supporting document "
                "to be attached."
            ),
        )
    ], []