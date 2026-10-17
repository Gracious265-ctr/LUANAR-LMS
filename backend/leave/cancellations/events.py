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


@dataclass(frozen=True)
class CancellationEvent:
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