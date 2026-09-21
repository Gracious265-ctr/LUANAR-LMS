"""Application-tracking service (Unit 15).

``get_application_tracking`` is the only access path to the read-only tracking
payload. It enforces employee ownership (404 for anyone else — never 403) and
the submitted-status gate (409 ``application_not_submitted`` for drafts), then
delegates workflow state to the configured tracking provider.

No audit records are read or written: the tracking payload is a live workflow
view with no audit-requirements (per the spec). The fixture provider performs
no database access, so ``assertNumQueries`` on the whole endpoint stays at one.
"""

from dataclasses import dataclass

from ..models import LeaveApplication
from .contracts import WorkflowTracking
from .provider import get_tracking_provider


class ApplicationNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class ApplicationNotSubmittedError(Exception):
    """The application is owned by the caller but has not been submitted."""


@dataclass
class TrackingPayload:
    """The application plus its workflow state, ready for serialization."""

    application: LeaveApplication
    workflow: WorkflowTracking


def get_application_tracking(user, application_id) -> TrackingPayload:
    """Return the tracking payload for ``user``'s submitted application.

    Raises ``ApplicationNotFoundError`` (404) when the application is missing or
    belongs to another employee, and ``ApplicationNotSubmittedError`` (409)
    when it is still a draft. Never raises a 403.
    """
    application = LeaveApplication.objects.filter(
        id=application_id, employee=user
    ).first()
    if application is None:
        raise ApplicationNotFoundError()
    if application.status != LeaveApplication.Status.SUBMITTED:
        raise ApplicationNotSubmittedError()

    workflow = get_tracking_provider().get_workflow_tracking(application)
    return TrackingPayload(application=application, workflow=workflow)