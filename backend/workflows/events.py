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