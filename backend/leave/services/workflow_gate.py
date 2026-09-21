"""Workflow readiness gate (Unit 14, unit-workflow).

Invariant 12.7 requires that a valid, configured workflow exists before an
application is submitted. Workflows do not exist yet (Units 6/7 are HR-track and
not merged), so this is a stub that always reports ready, with a ``TODO`` marker
for the unit that enforces the invariant.
"""


def check_workflow_ready(application) -> bool:
    """Return True when workflow routing is available for submission.

    TODO(unit-workflow): enforce invariant 12.7 here — a valid configured
    workflow must exist for the employee's category/department before the
    application may be submitted; return the workflow (and raise a structured
    error when missing) instead of ``True``.
    """
    return True