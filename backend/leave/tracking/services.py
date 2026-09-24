"""Application-tracking service (Unit 15).

``get_application_tracking`` is the only access path to the read-only tracking
payload. It enforces employee ownership (404 for anyone else — never 403) and
the submitted-status gate (409 ``application_not_submitted`` for drafts), then
delegates workflow state to the configured tracking provider.

Unit 18 extends the payload with cancellation state: the real application
status wins over the fixture scenario once it leaves ``submitted`` (so a
cancelled application reports ``cancelled``), and one extra query loads the
latest cancellation request. The fixture provider's own scenario load performs
no database access, so the owner endpoint totals two queries.
"""

from dataclasses import dataclass, replace

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
    if application.status == LeaveApplication.Status.DRAFT:
        raise ApplicationNotSubmittedError()

    workflow = get_tracking_provider().get_workflow_tracking(application)

    if application.status != LeaveApplication.Status.SUBMITTED:
        workflow = replace(workflow, status=application.status)
    if application.status == LeaveApplication.Status.CANCELLED:
        workflow = replace(workflow, cancelled_at=application.cancelled_at)

    workflow = replace(workflow, **_cancellation_state(application, user))
    return TrackingPayload(application=application, workflow=workflow)


def _cancellation_state(application, user) -> dict:
    """The cancellation facts appended to every tracking payload (Unit 18).

    One query loads the latest cancellation request; the open-request flag is
    derived from it (the partial unique constraint allows at most one pending).
    Eligibility is reused from the Unit 18 service so the payload and the
    cancellation endpoints can never disagree.
    """
    from leave.cancellations.models import CancellationRequest
    from leave.cancellations.services import get_eligibility

    latest = (
        CancellationRequest.objects.filter(application=application)
        .order_by("-requested_at")
        .first()
    )
    open_request = (
        latest
        if latest is not None
        and latest.status == CancellationRequest.Status.PENDING
        else None
    )
    eligibility = get_eligibility(application, user, open_request=open_request)

    return {
        "cancellation_action": eligibility.cancellation_action,
        "cancellation_blocked_reason": eligibility.cancellation_blocked_reason,
        "has_open_cancellation_request": open_request is not None,
        "latest_cancellation": (
            {
                "id": str(latest.id),
                "kind": latest.kind,
                "status": latest.status,
                "requested_at": _z(latest.requested_at),
                "decided_at": _z(latest.decided_at),
            }
            if latest is not None
            else None
        ),
    }


def _z(value):
    """Render a datetime as UTC ISO 8601 with a ``Z`` suffix, or ``None``."""
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")