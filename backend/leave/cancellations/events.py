<<<<<<< HEAD
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
=======
"""Cancellation domain events and notification state (Unit 18, spec 3.6).

``emit_cancellation_event`` is a broadcast sink on commit — the same shape as the
approval bus in Unit 16, with the notifications app connected as its first real
consumer. Consumers register themselves through :func:`register_consumer` (the
notifications app does so in ``ready()``) and each one owns its own failure
isolation: a raising consumer records its own ``failed`` state and must never
abort its siblings or the commit.

The notifications consumer also moves ``employee_notification_state`` through
:func:`set_notification_state`, so the request always says whether the employee
was actually reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: Signature of a consumer: ``callable(event) -> None``.
Consumer = Callable[[Any], None]

#: Ordered registry of consumers, appended by later units.
_consumers: list[Consumer] = []

CANCELLATION_REQUESTED = "cancellation.requested"
CANCELLATION_WITHDRAWN = "cancellation.withdrawn"
CANCELLATION_STAGE_APPROVED = "cancellation.stage_approved"
CANCELLATION_APPROVED = "cancellation.approved"
CANCELLATION_REJECTED = "cancellation.rejected"
>>>>>>> feature/plans-teams


@dataclass(frozen=True)
class CancellationEvent:
<<<<<<< HEAD
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
=======
    """One cancellation event, as an immutable value object."""

    kind: str
    application_id: str
    request_id: str
    outcome: str
    recipient_user_ids: list[int] = field(default_factory=list)


def register_consumer(consumer: Consumer) -> None:
    """Append a commit-bus consumer. Registering the same consumer twice is a
    programming error (surfaced loudly rather than silently duplicating)."""
    if consumer in _consumers:
        raise ValueError("Cancellation-event consumer is already registered.")
    _consumers.append(consumer)


def emit_cancellation_event(event: CancellationEvent) -> None:
    """Broadcast one cancellation event to every registered consumer.

    Runs on commit, so every consumer sees a durable request. Consumers run in
    registration order and each owns its own failure isolation.
    """
    for consumer in list(_consumers):
        try:
            consumer(event)
        except Exception:
            logger.exception(
                "Cancellation consumer %r failed on %s; the cancellation itself "
                "is unaffected.",
                consumer,
                event.kind,
            )


def _reset_consumers_for_tests() -> None:
    """Clear the registry so each test starts from a known bus."""
    _consumers.clear()


def _restore_consumers(previous: list[Consumer]) -> None:
    """Restore the registry a test replaced (used with ``addCleanup``)."""
    _consumers[:] = previous


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
>>>>>>> feature/plans-teams
