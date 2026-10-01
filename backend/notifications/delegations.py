"""Delegation lifecycle emails.

The approval bus (:mod:`workflows.events`) carries
:class:`~workflows.events.ApprovalEvent`, whose subject is always a leave
application, so delegation mail rides the same discipline on its own path:

* **Emitted on commit** — :func:`notify_delegation` registers through
  ``transaction.on_commit``, so mail can only be sent once the delegation row
  is durable. A rolled-back decision never mails anybody.
* **Idempotent** — one outbox row per ``(delegation, kind, role_label)`` via
  ``get_or_create``; a re-emitted event finds the existing row and returns
  without sending a second mail.
* **Isolated** — send failures record ``failed`` on the outbox row and are
  swallowed, so one dead email backend can never take down a delegation
  decision.
* **No role scrape** — every recipient is resolved from an id already on the
  delegation row (the approver and the nominated/confirmed delegate), never
  from "whoever holds the HR role".

Recipients are per party rather than one mail to everybody: ``role_label`` says
which side of the delegation the row is for, so the approver and the delegate
each get their own durable delivery record.
"""

from __future__ import annotations

from django.db import transaction

from .models import NotificationOutbox
from .services import NotificationSeamUnresolvableError

#: Delegation lifecycle kinds broadcast on commit.
DELEGATION_REQUESTED = "delegation_requested"
DELEGATION_APPROVED = "delegation_approved"
DELEGATION_REJECTED = "delegation_rejected"
DELEGATION_CANCELLED = "delegation_cancelled"

#: ``role_label`` values for delegation rows: which party the mail concerns.
APPROVER = "approver"
DELEGATE = "delegate"


def _period(delegation) -> str:
    if delegation.ends_on:
        return f"{delegation.starts_on.isoformat()} to {delegation.ends_on.isoformat()}"
    return f"from {delegation.starts_on.isoformat()} (open-ended)"


def _recipients(delegation, kind: str) -> list[tuple[str, object]]:
    """The ``(role_label, user)`` pairs that should hear about ``kind``.

    * ``delegation_requested`` — only the nominated delegate, and only if one
      was nominated. The requester already knows they asked.
    * ``delegation_rejected`` / ``delegation_cancelled`` — the approver, plus
      the delegate when the row names one (a rejected request may only name a
      *nominee*; a cancelled delegation names a confirmed delegate).
    * ``delegation_approved`` — both sides: the approver learns their cover is
      live, the delegate learns they are now acting.
    """
    approver = delegation.approver
    delegate = delegation.delegate
    if kind == DELEGATION_REQUESTED:
        return [(DELEGATE, delegate)] if delegate is not None else []
    if kind == DELEGATION_APPROVED:
        return [(APPROVER, approver), (DELEGATE, delegate)]
    return (
        [(APPROVER, approver), (DELEGATE, delegate)]
        if delegate is not None
        else [(APPROVER, approver)]
    )


def compose_subject(delegation, kind: str) -> str:
    """Subject built from the persisted delegation row."""
    verb = {
        DELEGATION_REQUESTED: "nominated as delegate",
        DELEGATION_APPROVED: "approved",
        DELEGATION_REJECTED: "rejected",
        DELEGATION_CANCELLED: "cancelled",
    }[kind]
    return f"LUANAR delegation {verb} — {delegation.approver.get_full_name()}"


def compose_body(delegation, kind: str, role_label: str) -> str:
    """Plain-text body naming the covered approver, delegate, and period."""
    approver = delegation.approver.get_full_name()
    delegate = (
        delegation.delegate.get_full_name() if delegation.delegate_id else "not assigned"
    )
    if kind == DELEGATION_REQUESTED:
        headline = f"You were nominated to act as delegate for {approver}."
    elif kind == DELEGATION_APPROVED:
        if role_label == DELEGATE:
            headline = f"You are now acting as delegate for {approver}."
        else:
            headline = f"Your delegation to {delegate} was approved."
    elif kind == DELEGATION_REJECTED:
        headline = f"The delegation request for {approver} was rejected."
    else:
        headline = f"The delegation for {approver} was cancelled."

    lines = [
        headline,
        f"Period: {_period(delegation)}",
        f"Approver: {approver}",
        f"Delegate: {delegate}",
        f"State: {delegation.state}",
    ]
    if kind != DELEGATION_REQUESTED and delegation.decision_reason:
        lines.append(f"HR reason: {delegation.decision_reason}")
    elif delegation.request_reason and role_label == DELEGATE:
        lines.append(f"Request reason: {delegation.request_reason}")
    return "\n".join(lines) + "\n"


def _load_delegation(delegation_id: int):
    from workflows.models import Delegation

    delegation = (
        Delegation.objects.select_related("approver", "delegate")
        .filter(pk=delegation_id)
        .first()
    )
    if delegation is None:
        raise NotificationSeamUnresolvableError(
            f"Unresolvable delegation {delegation_id}."
        )
    return delegation


def queue_delegation_email(delegation_id: int, kind: str) -> None:
    """Record one delegation email per interested party and queue delivery.

    The subject is re-read from the database rather than taken from the caller,
    so the mail always describes the durable state.
    """
    from .tasks import enqueue_delivery

    delegation = _load_delegation(delegation_id)

    for role_label, user in _recipients(delegation, kind):
        if user is None or not user.email:
            continue
        row, created = NotificationOutbox.objects.get_or_create(
            delegation_id=delegation.pk,
            kind=kind,
            role_label=role_label,
            defaults={
                "recipient_email": user.email,
                "subject": compose_subject(delegation, kind),
                "body": compose_body(delegation, kind, role_label),
            },
        )
        if not created:
            continue  # already delivered in a previous broadcast — idempotent

        enqueue_delivery(row, recipients=[row.recipient_email])


def notify_delegation(delegation_id: int, kind: str) -> None:
    """Queue delegation mail once the surrounding transaction has committed."""

    def _run() -> None:
        try:
            queue_delegation_email(delegation_id, kind)
        except Exception:
            return  # a dead consumer must never surface at the call site

    transaction.on_commit(_run)
