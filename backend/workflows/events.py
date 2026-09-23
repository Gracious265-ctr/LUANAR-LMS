"""Approval event bus hook (Unit 16).

Decisions are broadcast on commit so observers (notifications, other track)
can react without coupling the decision service to any sink. ``emit_approval_event``
is a no-op in Unit 16; later units connect real consumers here.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def emit_approval_event(event: ApprovalEvent) -> None:
    """Broadcast an approval event on commit (no-op sink in Unit 16)."""
    return None