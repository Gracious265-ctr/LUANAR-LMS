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


@dataclass(frozen=True)
class ApprovalEvent:
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
