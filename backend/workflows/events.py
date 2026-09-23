"""Approval domain-event dispatcher (Unit 16, section 5 step 8).

``emit_approval_event`` is a documented hook where later units attach
notifications, annual-balance deduction and approved-document generation.
Unit 16 emits typed events but does nothing with them — no balance is deducted
and no email is sent (invariant 12.4 and the scope boundaries).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

EventKind = Literal["decision_recorded", "stage_assigned", "application_finalised"]


@dataclass(frozen=True)
class ApprovalEvent:
    """A typed, completed approval transition ready for downstream consumers."""

    kind: EventKind
    application_id: str
    stage_order: int
    action: str
    cycle: int
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


def emit_approval_event(event: ApprovalEvent) -> None:
    """Deliver an approval event to downstream subscribers.

    Currently a no-op so Unit 16 updates serialized application state in place
    while remaining side-effect free. Later units subscribe here for
    notifications, balance deduction (after final approval only) and document
    generation.
    """
    return None