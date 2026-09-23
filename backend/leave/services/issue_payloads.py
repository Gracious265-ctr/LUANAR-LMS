"""Shared error-list payload helpers for leave endpoints."""


def issue_payload(issue) -> dict:
    """Render one ``ValidationIssue`` in the shared error convention.

    The Unit 1 convention is ``{code, field, message, detail}``; the Unit 17
    resubmit spec serializes ``{code, message, field}``. Returning all four is
    additive and compatible with both consumers.
    """
    return {
        "code": issue.code,
        "field": issue.field,
        "message": issue.message,
        "detail": issue.detail,
    }