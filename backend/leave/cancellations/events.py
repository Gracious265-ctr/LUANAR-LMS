"""Cancellation domain events (Unit 18, section 3.6).

``emit`` is a no-op by default (consistent with Units 16 and 17).
Future notification apps will subscribe to these events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

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
    """Deliver a cancellation event to downstream subscribers.

    Currently a no-op so the cancellation flow remains side-effect free.
    Future units subscribe here for notifications.
    """
    return None


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