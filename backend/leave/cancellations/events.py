"""Cancellation domain events and notification state (Unit 18, spec 3.6).

``emit_cancellation_event`` is a no-op sink broadcast on commit — consistent
with Units 16/17 (no emails in this unit). The future notifications app reads
``employee_notification_state`` and calls :func:`set_notification_state` to move
it ``pending -> sent | failed``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils.module_loading import import_string

CANCELLATION_REQUESTED = "cancellation.requested"
CANCELLATION_WITHDRAWN = "cancellation.withdrawn"
CANCELLATION_STAGE_APPROVED = "cancellation.stage_approved"
CANCELLATION_APPROVED = "cancellation.approved"
CANCELLATION_REJECTED = "cancellation.rejected"


@dataclass(frozen=True)
class CancellationEvent:
    """One cancellation event, as an immutable value object."""

    kind: str
    application_id: str
    request_id: str
    outcome: str
    recipient_user_ids: list[int] = field(default_factory=list)


def emit_cancellation_event(event: CancellationEvent) -> None:
    """Broadcast a cancellation event on commit (no-op sink in Unit 18)."""
    # Reconciliation note: at Unit 20 the real notification consumers connect
    # here; until then this is intentionally a no-op consistent with Units 16/17.
    return None


def set_notification_state(request_id, state: str):
    """Move a request's ``employee_notification_state`` pending -> sent | failed.

    This is the single entry point the notifications app (or a test) uses to
    flip the state. Returns the updated request.
    """
    from .models import CancellationRequest

    allowed = (
        CancellationRequest.NotificationState.SENT,
        CancellationRequest.NotificationState.FAILED,
    )
    if state not in allowed:
        raise ValueError("Notification state must be sent or failed.")
    request = CancellationRequest.objects.filter(id=request_id).first()
    if request is None:
        raise CancellationRequest.DoesNotExist
    CancellationRequest.objects.filter(id=request_id).update(
        employee_notification_state=state
    )
    request.refresh_from_db(fields=["employee_notification_state"])
    return request