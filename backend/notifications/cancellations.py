"""Cancellation-request emails.

The cancellation bus (:mod:`leave.cancellations.events`) broadcasts one event per
state change on commit; this module turns each into an outbox row and hands it to
:mod:`notifications.tasks`. Same discipline as the decision composer:

* **Idempotent** — ``get_or_create`` on ``(cancellation, kind, role_label)``, so a
  replayed or re-broadcast event finds the existing row and sends nothing twice.
* **Isolated** — the row is written here, the send happens in the task, and
  ``set_notification_state`` records the outcome on the request itself, so
  "did the employee hear?" is answerable without a shell.

The employee is the audience for every cancellation event: they are the one whose
leave changed. ``recipient_user_ids`` on the event carries the employee plus the
original workflow members (used for audit context, not for extra mail), so this
module deliberately sends exactly one email per event.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

from leave.cancellations.events import (
    CANCELLATION_APPROVED,
    CANCELLATION_REJECTED,
    CANCELLATION_REQUESTED,
    CANCELLATION_STAGE_APPROVED,
    CANCELLATION_WITHDRAWN,
    CancellationEvent,
)
from notifications.models import NotificationOutbox

logger = logging.getLogger(__name__)

KIND_CANCELLATION_REQUESTED = "cancellation_requested"
KIND_CANCELLATION_STAGE_APPROVED = "cancellation_stage_approved"
KIND_CANCELLATION_APPROVED = "cancellation_approved"
KIND_CANCELLATION_REJECTED = "cancellation_rejected"
KIND_CANCELLATION_WITHDRAWN = "cancellation_withdrawn"

ROLE_EMPLOYEE = "employee"

#: Event kind → outbox kind. The dotted event vocabulary stays on the bus; the
#: outbox uses the same underscore style as the other composers.
_KINDS = {
    CANCELLATION_REQUESTED: KIND_CANCELLATION_REQUESTED,
    CANCELLATION_STAGE_APPROVED: KIND_CANCELLATION_STAGE_APPROVED,
    CANCELLATION_APPROVED: KIND_CANCELLATION_APPROVED,
    CANCELLATION_REJECTED: KIND_CANCELLATION_REJECTED,
    CANCELLATION_WITHDRAWN: KIND_CANCELLATION_WITHDRAWN,
}

_HEADLINES = {
    KIND_CANCELLATION_REQUESTED: "Cancellation request received",
    KIND_CANCELLATION_STAGE_APPROVED: "Cancellation approved at your stage",
    KIND_CANCELLATION_APPROVED: "Cancellation approved",
    KIND_CANCELLATION_REJECTED: "Cancellation rejected",
    KIND_CANCELLATION_WITHDRAWN: "Cancellation withdrawn",
}


def _request(event: CancellationEvent):
    from leave.cancellations.models import CancellationRequest

    return CancellationRequest.objects.select_related(
        "application", "requested_by"
    ).filter(pk=event.request_id).first()


def _employee_email(event: CancellationEvent) -> str | None:
    """The employee on the cancelled application — resolved from the record."""
    request = _request(event)
    if request is None:
        return None
    application = request.application
    if application is None or application.employee_id is None:
        return None
    employee = get_user_model().objects.filter(pk=application.employee_id).first()
    if employee is None or not employee.email:
        return None
    return employee.email


def _reference(request) -> str:
    """The application reference, falling back to its id.

    ``reference_number`` is assigned on submission, so a mail that reaches a human
    always has one; the fallback only matters for rows created outside the
    submission path (seeds, tests) and keeps the body from saying "None".
    """
    application = request.application
    return application.reference_number or f"application {application.pk}"


def _latest_decision(request):
    """The most recently decided approval stage, if any.

    A rejection or an approval email is useless without "who decided, and why",
    so the stage that produced the event is read back from the request rather
    than guessed from the event's dotted kind.
    """
    return (
        request.stages.filter(decided_at__isnull=False)
        .select_related("approver")
        .order_by("-decided_at", "-order")
        .first()
    )


def _compose_subject(kind: str, request) -> str:
    return (
        f"LUANAR leave cancellation — {_reference(request)} {_HEADLINES[kind]}"
    )[:200]


def _compose_body(kind: str, request, event: CancellationEvent) -> str:
    from leave.cancellations.models import CancellationRequest

    application = request.application
    requested_by = request.requested_by
    requested_by_name = (
        requested_by.get_full_name() if requested_by is not None else "an approver"
    )
    lines = [
        f"Reference: {_reference(request)}",
        f"Outcome: {_HEADLINES[kind]}",
        f"Request type: {CancellationRequest.Kind(request.kind).label}",
        f"Requested by: {requested_by_name}",
        f"Reason: {request.reason or '-'}",
        f"Request state: {CancellationRequest.Status(request.status).label}",
    ]
    if kind in (
        KIND_CANCELLATION_STAGE_APPROVED,
        KIND_CANCELLATION_APPROVED,
        KIND_CANCELLATION_REJECTED,
    ):
        stage = _latest_decision(request)
        if stage is not None:
            decider = (
                stage.approver.get_full_name() if stage.approver is not None else "-"
            )
            lines.append(f"Decided by: {decider} ({stage.role_label})")
            lines.append(f"Decision note: {stage.comment or '-'}")
    if kind == KIND_CANCELLATION_REJECTED:
        lines.append("Your leave dates were left unchanged.")
    elif kind == KIND_CANCELLATION_WITHDRAWN:
        lines.append("The pending application was withdrawn; no approval was needed.")
    elif kind == KIND_CANCELLATION_APPROVED:
        if request.balance_restored_days:
            lines.append(
                f"Restored to your leave balance: {request.balance_restored_days} "
                f"day(s) ({request.restored_financial_year or 'current year'})."
            )
        lines.append("Your leave dates were cancelled.")
    elif kind == KIND_CANCELLATION_STAGE_APPROVED:
        lines.append("Your application is still with the remaining approvers.")
    elif kind == KIND_CANCELLATION_REQUESTED:
        lines.append("It is now with the approvers for a decision.")
    lines.append(f"Leave dates: {application.start_date} to {application.end_date}")
    return "\n".join(lines) + "\n"


def queue_cancellation_email(event: CancellationEvent) -> None:
    """Record one cancellation email and queue it for the employee."""
    from notifications.tasks import enqueue_delivery

    kind = _KINDS.get(event.kind)
    if kind is None:
        logger.warning(
            "No cancellation outbox kind for event %r; nothing queued.", event.kind
        )
        return

    request = _request(event)
    if request is None:
        logger.error(
            "Cancellation request %s no longer exists; nothing queued.",
            event.request_id,
        )
        return

    recipient = _employee_email(event)
    if not recipient:
        logger.warning(
            "Cancellation request %s has no reachable employee email; nothing "
            "queued.",
            event.request_id,
        )
        return

    row, created = NotificationOutbox.objects.get_or_create(
        cancellation_id=event.request_id,
        kind=kind,
        role_label=ROLE_EMPLOYEE,
        defaults={
            "recipient_email": recipient,
            "subject": _compose_subject(kind, request),
            "body": _compose_body(kind, request, event),
        },
    )
    if not created:
        return  # already emitted in a previous broadcast — idempotent

    enqueue_delivery(row, recipients=[recipient])
    _mark_pending(request)


def register_cancellation_email_consumer() -> None:
    """Attach the cancellation email composer to the cancellation bus."""
    from leave.cancellations.events import register_consumer

    register_consumer(queue_cancellation_email)


# --- employee_notification_state -----------------------------------------


def _mark_pending(request) -> None:
    """Record that an email is owed, so the request is honest while it waits.

    Written with ``update`` rather than ``save`` because the request is already
    durable and this is bookkeeping about the notification, not about the
    cancellation: a replay must not bump ``updated_at`` on a decided request.
    """
    from leave.cancellations.models import CancellationRequest

    if request.employee_notification_state in (
        CancellationRequest.NotificationState.PENDING,
        CancellationRequest.NotificationState.SENT,
    ):
        return  # already owed, or already confirmed; never walk a delivery back
    # ``not_required`` / ``failed`` → owed again (a replay after a failure, or the
    # first event for this request).
    CancellationRequest.objects.filter(pk=request.pk).update(
        employee_notification_state=CancellationRequest.NotificationState.PENDING
    )


def _confirm_delivered(request_id: str, state: str) -> None:
    """Move ``employee_notification_state`` pending → sent | failed.

    Called by the delivery task through :func:`confirm_cancellation_delivery`;
    kept here so the vocabulary check lives next to the composers.
    """
    from leave.cancellations.events import set_notification_state
    from leave.cancellations.models import CancellationRequest

    if state not in (
        CancellationRequest.NotificationState.SENT,
        CancellationRequest.NotificationState.FAILED,
    ):
        return
    if not CancellationRequest.objects.filter(pk=request_id).exists():
        return
    set_notification_state(request_id, state)


def confirm_cancellation_delivery(outbox_id) -> None:
    """Report one cancellation row's delivery outcome back onto its request.

    The outbox is the delivery record; the request's
    ``employee_notification_state`` is what the product and the API surface, so
    the two are reconciled here after every send attempt.
    """
    row = NotificationOutbox.objects.filter(pk=outbox_id).only(
        "cancellation_id", "state"
    ).first()
    if row is None or row.cancellation_id is None:
        return
    _confirm_delivered(str(row.cancellation_id), row.state)
