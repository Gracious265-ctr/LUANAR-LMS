<<<<<<< HEAD
"""Notification service (Unit 22, section 2).

``send_notification`` persists one :class:`Notification` row per eligible
recipient (active user with an email address) and enqueues delivery through
django-q2. It never sends mail synchronously and never re-queries business
logic. Tests patch ``async_task`` or run ``deliver_notification`` directly;
``send_sync_callbacks`` lets a test (or dev tool) observe the created rows.
"""

from django_q.tasks import async_task

from users.models import User

from .models import Notification


def send_notification(
    *,
    event_type: str,
    recipients,
    subject: str,
    body: str,
    application_id=None,
    target_object_id=None,
    send_sync_callbacks=(),
):
    """Persist and enqueue one email per eligible recipient.

    ``recipients`` may be a sequence of users; inactive users and users
    without an email are skipped. Returns the created ``Notification`` rows.
    """
    user_ids = {user.pk for user in recipients}
    eligible = list(
        User.objects.filter(pk__in=user_ids, is_active=True).exclude(
            email__exact=""
        )
    )
    if not eligible:
        return []

    rows = [
        Notification.objects.create(
            event_type=event_type,
            recipient=user,
            email_to=user.email,
            subject=subject,
            body=body,
            application_id=application_id,
            target_object_id=target_object_id,
        )
        for user in eligible
    ]

    for row in rows:
        async_task("notifications.tasks.deliver_notification", row.id)

    for callback in send_sync_callbacks:
        callback(rows)

    return rows
=======
"""Unit 22 — decision-email consumer (the first real approval-bus consumer).

``queue_decision_email`` is registered on the Unit 16 approval-event bus (now a
real registry). ``decide()`` emits on commit, so this runs only after the
decision is durable. Discipline:

* **Idempotent** — the outbox row is found with ``get_or_create`` on
  ``(application, kind, submission_cycle, role_label)``; a re-emitted event
  finds the existing row and returns without queueing a second email.
* **Isolated** — this module only writes the row and hands it to
  :mod:`notifications.tasks`, where the send happens. A delivery failure records
  ``failed`` on the outbox row and is logged; it can never take down the decision
  commit.
* **Transport from settings** — the backend is whatever ``EMAIL_BACKEND`` says
  (console until ``.env`` configures a relay). No SMTP credentials in the tree.
"""

from __future__ import annotations

from workflows.events import APPLICATION_FINALISED, ApprovalEvent

#: The domain these notifications belong to (kept in the body/subject for now).
#: The send site in :mod:`notifications.tasks` uses it for the fallback
#: ``From:`` address when no relay is configured.
LEAVE_DOMAIN = "luanar.ac.mw"


def compose_subject(event: ApprovalEvent) -> str:
    """Subject from the persisted event vocabulary."""
    return (
        f"LUANAR leave decision — {event.reference_number} "
        f"{event.action} ({event.role_label})"
    )


def compose_body(event: ApprovalEvent) -> str:
    """Plain-text decision body built from the persisted ``ApprovalEvent`` atoms."""
    return (
        f"Reference: {event.reference_number}\n"
        f"Decision: {event.action}\n"
        f"Role: {event.role_label} (stage {event.stage_order}, "
        f"cycle {event.submission_cycle})\n"
        f"Approver: {event.approver_name}\n"
        f"Comment: {event.comment or '-'}\n"
    )


def _application_owner_email(event: ApprovalEvent) -> str:
    """Owner email resolved from the persisted application record."""
    from leave.models import LeaveApplication

    application = LeaveApplication.objects.filter(pk=event.application_id).first()
    if application is None or application.employee_id is None:
        raise NotificationSeamUnresolvableError(
            f"Unresolvable owner for application {event.application_id}."
        )
    return application.employee.email


def _decision_recipients(event: ApprovalEvent) -> list[str]:
    """Recipient matrix (D4).

    ``DECISION_RECORDED`` → the employee (owner). ``APPLICATION_FINALISED`` →
    the owner plus the approver who finalised. The approver email is resolved
    from the persisted user id, never from a role scrape.
    """
    recipients = [_application_owner_email(event)]
    if event.kind == APPLICATION_FINALISED and event.approver_id:
        from django.contrib.auth import get_user_model

        approver = get_user_model().objects.filter(pk=event.approver_id).first()
        if approver is not None and approver.email:
            recipients.append(approver.email)
    return recipients


def queue_decision_email(event: ApprovalEvent) -> None:
    """Record one decision email and hand it to the delivery task.

    The row is written here; :func:`notifications.tasks.deliver_notification`
    sends it. ``DECISION_RECORDED`` therefore lands in the outbox as ``pending``
    and reaches the owner as soon as a worker picks it up — the decision it
    describes is already durable either way.
    """
    from notifications.models import NotificationOutbox
    from notifications.tasks import enqueue_delivery

    recipients = _decision_recipients(event)
    row, created = NotificationOutbox.objects.get_or_create(
        application_id=event.application_id,
        kind=event.kind,
        submission_cycle=event.submission_cycle,
        role_label=event.role_label,
        defaults={
            "recipient_email": recipients[0],
            "subject": compose_subject(event),
            "body": compose_body(event),
        },
    )
    if not created:
        return  # already delivered in a previous broadcast — idempotent

    # The row records the owner as its subject; a finalised application also goes
    # to the approver who finalised, so the full list travels with the task
    # rather than being re-derived from the row.
    enqueue_delivery(row, recipients=recipients)


def register_decision_email_consumer() -> None:
    """Attach the email dispatcher to the Unit 16 bus."""
    from workflows.events import register_consumer

    register_consumer(queue_decision_email)


class NotificationSeamUnresolvableError(Exception):
    """Raised when an email recipient cannot be resolved from the record."""
>>>>>>> feature/plans-teams
