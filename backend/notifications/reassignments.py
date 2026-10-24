"""HR reassignment emails.

A reassignment silently moves a pending application between two people's queues,
so it carries the same delivery discipline as the delegation path
(:mod:`notifications.delegations`):

* **Emitted on commit** — :func:`notify_reassignment` registers through
  ``transaction.on_commit``, so mail can only be sent once the ``Reassignment``
  row and the moved ``current_approver`` spine are durable. A rolled-back
  reassignment never mails anybody.
* **Idempotent** — one outbox row per ``(reassignment, kind, role_label)`` via
  ``get_or_create``. The row hangs off the *reassignment*, not the application,
  so an application reassigned several times in one submission cycle still gets
  one mail per intervention.
* **Isolated** — send failures record ``failed`` on the outbox row and are
  swallowed, so one dead email backend can never roll back an HR intervention.
* **No role scrape** — every recipient is resolved from an id already on the
  reassignment row (``from_approver`` / ``to_approver``), never from "whoever
  holds the HR role".

Both approvers are told, because both of their queues just changed:

* the **replacement** learns they now own a pending application they did not
  ask for, and
* the **previous** approver learns it was taken off them before they acted.

The employee is deliberately *not* mailed. They already see the reassignment on
their tracking timeline as a ``reassigned`` event (Unit 15), and the only thing
this mail would add is HR's internal reason, which that view is not the right
place to repeat.
"""

from __future__ import annotations

from django.db import transaction

from .models import NotificationOutbox
from .services import NotificationSeamUnresolvableError

#: Reassignment kinds broadcast on commit.
APPLICATION_REASSIGNED = "application_reassigned"

#: ``role_label`` values: which side of the move the mail concerns.
FROM_APPROVER = "from_approver"
TO_APPROVER = "to_approver"


def _recipients(reassignment) -> list[tuple[str, object]]:
    """The ``(role_label, user)`` pairs that should hear about the move.

    The previous approver is skipped when the row records an *initial*
    assignment (``from_approver`` is ``None``) — nobody lost a queue that never
    existed, so mailing them would be noise.
    """
    pairs = [(TO_APPROVER, reassignment.to_approver)]
    if reassignment.from_approver_id is not None:
        pairs.insert(0, (FROM_APPROVER, reassignment.from_approver))
    return pairs


def compose_subject(reassignment) -> str:
    """Subject built from the persisted reassignment row."""
    reference = reassignment.application.reference_number or "a leave application"
    return f"LUANAR leave reassigned — {reference}"


def compose_body(reassignment, role_label: str) -> str:
    """Plain-text body naming the application, the move, and HR's reason."""
    application = reassignment.application
    previous = (
        reassignment.from_approver.get_full_name()
        if reassignment.from_approver_id
        else "nobody (first assignment)"
    )
    if role_label == TO_APPROVER:
        headline = (
            f"You have been assigned {application.employee.get_full_name()}'s "
            "pending leave application."
        )
    else:
        headline = (
            f"{application.employee.get_full_name()}'s pending leave "
            "application was reassigned away from you."
        )

    lines = [
        headline,
        f"Reference: {application.reference_number or '—'}",
        f"Leave type: {_leave_type_name(application) or '—'}",
        f"Dates: {application.start_date or '—'} to {application.end_date or '—'}",
        f"Previous approver: {previous}",
        f"New approver: {reassignment.to_approver.get_full_name()}",
        f"Reassigned by: {reassignment.decided_by.get_full_name()}",
    ]
    if reassignment.reason:
        lines.append(f"HR reason: {reassignment.reason}")
    return "\n".join(lines) + "\n"


def _leave_type_name(application) -> str:
    """Resolve the application's leave type.

    ``LeaveApplication.leave_type_id`` is a soft integer reference, not an FK
    (the FK upgrade is an integration-track concern), so the name needs the same
    ``LeaveType`` lookup the pending-queue serializer does.
    """
    from leave_types.models import LeaveType

    if not application.leave_type_id:
        return ""
    return (
        LeaveType.objects.filter(pk=application.leave_type_id)
        .values_list("name", flat=True)
        .first()
        or ""
    )


def _load_reassignment(reassignment_id: int):
    from approvals.models import Reassignment

    reassignment = (
        Reassignment.objects.select_related(
            "application__employee",
            "from_approver",
            "to_approver",
            "decided_by",
        )
        .filter(pk=reassignment_id)
        .first()
    )
    if reassignment is None:
        raise NotificationSeamUnresolvableError(
            f"Unresolvable reassignment {reassignment_id}."
        )
    return reassignment


def queue_reassignment_email(reassignment_id: int) -> None:
    """Record one reassignment email per affected approver and queue delivery.

    The subject is re-read from the database rather than taken from the caller,
    so the mail always describes the durable state.
    """
    from .tasks import enqueue_delivery

    reassignment = _load_reassignment(reassignment_id)

    for role_label, user in _recipients(reassignment):
        if user is None or not user.email:
            continue
        row, created = NotificationOutbox.objects.get_or_create(
            reassignment_id=reassignment.pk,
            kind=APPLICATION_REASSIGNED,
            role_label=role_label,
            defaults={
                "recipient_email": user.email,
                "subject": compose_subject(reassignment),
                "body": compose_body(reassignment, role_label),
            },
        )
        if not created:
            continue  # already delivered in a previous broadcast — idempotent

        enqueue_delivery(row, recipients=[row.recipient_email])


def notify_reassignment(reassignment_id: int) -> None:
    """Queue reassignment mail once the surrounding transaction has committed."""

    def _run() -> None:
        try:
            queue_reassignment_email(reassignment_id)
        except Exception:
            return  # a dead consumer must never surface at the call site

    transaction.on_commit(_run)
