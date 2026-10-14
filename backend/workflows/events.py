<<<<<<< HEAD
"""Approval, delegation and reassignment domain-event dispatchers.

Unit 16 emits typed approval events but nothing consumed them (no balance is
deducted and no email is sent by any decision here). Unit 22 routes every
event through the notification dispatcher (see ``notifications/dispatcher.py``);
the dataclass contracts are unchanged and every ``emit_*`` function still
returns ``None`` so the side-effect-free event contract holds.

Unit 23 finalises a finally-approved application: the annual-leave balance
deduction and the official approved-leave PDF are produced in
``documents.finalisation.finalise_approved_application``, called here for
``application_finalised`` events only. It is gated by
``settings.APPROVAL_FINALISATION`` (``"on"`` by default, ``"off"`` in the test
settings) so the rest of the suite stays free of ledger rows and stored files.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from django.conf import settings

from notifications.dispatcher import dispatch

EventKind = Literal["decision_recorded", "stage_assigned", "application_finalised"]
=======
"""Approval event bus (Unit 16 seam → real registry in Unit 22).

Decisions are broadcast on commit so observers (notifications, other track)
can react without coupling the decision service to any sink. ``decide()`` calls
``emit_approval_event`` from inside ``transaction.on_commit`` (see Unit 16 §6.1
D4), so every consumer runs only after the decision row is durable.

Unit 16 left the bus as a no-op sink; Unit 22 connects the first real consumer
(email notifications) via ``register_consumer``. Later units add theirs to the
same registry — the dispatcher stays order-independent and one event may fan
out to many consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

#: Signature of a consumer: ``callable(event) -> None``. A consumer owns its own
#: failure state and must never let an exception escape the commit boundary.
Consumer = Callable[[Any], None]

#: Ordered registry of consumers, appended by later units.
_consumers: list[Consumer] = []
>>>>>>> feature/plans-teams


@dataclass(frozen=True)
class ApprovalEvent:
<<<<<<< HEAD
    """A typed, completed approval transition ready for downstream consumers."""

    kind: EventKind
    application_id: str
    stage_order: int
    action: str
    cycle: int
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DelegationEvent:
    """A delegation request decided by HR (approved / rejected / cancelled)."""

    event_name: Literal["delegation.approved", "delegation.rejected", "delegation.cancelled"]
    delegation_id: str
    approver_user_id: int
    delegate_user_id: int | None
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReassignmentEvent:
    """An HR emergency reassignment of a pending application to an approver."""

    reassignment_id: str
    application_id: str
    from_approver_user_id: int | None
    to_approver_user_id: int
    employee_user_id: int
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


def emit_approval_event(event: ApprovalEvent) -> None:
    """Deliver an approval event to the notification subscriber."""
    dispatch("approval", event)
    if event.kind == "application_finalised" and _finalisation_enabled():
        from documents.finalisation import finalise_approved_application

        finalise_approved_application(event.application_id)
    return None


def emit_delegation_event(event: DelegationEvent) -> None:
    """Deliver a delegation event to the notification subscriber."""
    return dispatch("delegation", event)


def emit_reassignment_event(event: ReassignmentEvent) -> None:
    """Deliver a reassignment event to the notification subscriber."""
    return dispatch("reassignment", event)


def _finalisation_enabled() -> bool:
    return (getattr(settings, "APPROVAL_FINALISATION", "on") or "on").strip() != "off"
=======
    """One recorded decision, as an immutable value object."""

    kind: str
    application_id: str
    reference_number: str
    action: str
    stage_order: int
    role_label: str
    approver_id: int
    approver_name: str
    comment: str
    submission_cycle: int


#: Decision kinds broadcast on commit.
DECISION_RECORDED = "decision_recorded"
APPLICATION_FINALISED = "application_finalised"


def register_consumer(consumer: Consumer) -> None:
    """Append a commit-bus consumer. Registering the same consumer twice is a
    programming error (surfaced loudly rather than silently duplicating)."""
    if consumer in _consumers:
        raise ValueError("Approval-event consumer is already registered.")
    _consumers.append(consumer)


def emit_approval_event(event: ApprovalEvent) -> None:
    """Broadcast one approval event to every registered consumer.

    Runs on commit (Unit 16 D4). Consumers run in registration order and each
    owns its own failure isolation — a raising consumer records its own
    ``failed`` state (Unit 22 outbox discipline) and must never abort the
    siblings or the commit, so the exception is swallowed here.
    """
    for consumer in list(_consumers):
        try:
            consumer(event)
        except Exception:
            continue


def _reset_consumers_for_tests() -> None:
    """Clear the registry so each test starts from a known bus."""
    _consumers.clear()
>>>>>>> feature/plans-teams
