"""Workflow readiness gate (Unit 21).

Invariant 12.7 requires that a valid, configured workflow exists before an
application is submitted. ``check_workflow_ready`` resolves the applicable HR
workflow for the employee's category/department and verifies every stage can
resolve an active approver, raising :class:`WorkflowUnavailableError` with the
reasons otherwise. Submission maps that error to the ``workflow_unavailable``
validation code before any draft leaves the employee's hands.
"""


class WorkflowUnavailableError(Exception):
    """No satisfiable workflow exists for the application; carries messages."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


def check_workflow_ready(application) -> bool:
    """Return True when workflow routing is available for submission.

    Raises :class:`WorkflowUnavailableError` (with human-readable messages)
    when no workflow applies to the employee's category/department or a stage
    has no active approver.
    """
    from workflows.providers import WorkflowConfigError, get_workflow_provider

    try:
        definitions = get_workflow_provider().get_stage_definitions(application)
    except WorkflowConfigError as exc:
        raise WorkflowUnavailableError([str(exc)])

    if not definitions:
        raise WorkflowUnavailableError(
            ["No approval workflow is configured for submission."]
        )

    # A section with no eligible approver is a configuration error, and a
    # well-formed provider raises ``WorkflowConfigError`` naming the section
    # rather than returning an empty set. This check is the belt to that
    # braces: a provider that returns an empty set has still failed the gate,
    # and the message has to say which step is stranded.
    missing = [
        f'No active approver for the "{definition.role_label}" approval section.'
        for definition in definitions
        if not definition.approver_user_ids
    ]
    if missing:
        raise WorkflowUnavailableError(missing)
    return True