"""Cancellation domain events (Unit 18, section 3.6).

Unit 22 wires ``emit`` to the notification dispatcher so cancellations and
withdrawals produce emails; ``set_notification_state`` records on the request
whether the employee-facing notification was delivered.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from notifications.dispatcher import dispatch

CancellationEventName = Literal[
    "cancellation.requested",
    "cancellation.withdrawn",
    "cancellation.stage_approved",
    "cancellation.approved",
    "cancellation.rejected",
]


@dataclass(frozen=True)
class CancellationEvent:
    """A typed cancellation event payload."""

    event_name: CancellationEventName
    application_id: str
    request_id: str
    outcome: str
    recipient_user_ids: list[int]
    occurred_at: datetime = field(default_factory=datetime.now)
    payload: dict = field(default_factory=dict)


def emit(event_name: CancellationEventName, payload: dict) -> None:
    """Deliver a cancellation event to the notification subscriber."""
    event = CancellationEvent(
        event_name=event_name,
        application_id=payload["application_id"],
        request_id=payload["request_id"],
        outcome=payload["outcome"],
        recipient_user_ids=payload["recipient_user_ids"],
        payload=payload,
    )
    return dispatch("cancellation", event)


def set_notification_state(request_id: str, state: str) -> None:
    """Move ``employee_notification_state`` from pending to sent | failed.

    Entry point the future notifications app will call.
    """
    from ..models import CancellationRequest

    try:
        request_obj = CancellationRequest.objects.get(id=request_id)
        request_obj.employee_notification_state = state
        request_obj.save(update_fields=["employee_notification_state"])
    except CancellationRequest.DoesNotExist:
        pass