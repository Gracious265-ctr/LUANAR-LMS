"""Unit 22 — decision-email consumer (the first real approval-bus consumer).

``send_decision_email`` is registered on the Unit 16 approval-event bus (now a
real registry). ``decide()`` emits on commit, so this runs only after the
decision is durable. Discipline:

* **Idempotent** — the outbox row is found with ``get_or_create`` on
  ``(application, kind, submission_cycle, role_label)``; a re-emitted event
  finds the existing row and returns without sending a second email.
* **Isolated** — send failures record ``failed`` on the outbox row and are
  swallowed so one dead email backend can never take down the decision commit.
* **Console backend in dev** — ``EMAIL_BACKEND`` is ``console``; tests assert
  through Django's ``mail.outbox``. No SMTP credentials in the tree.
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail

from workflows.events import APPLICATION_FINALISED, ApprovalEvent

#: The domain this notification belongs to (kept in the body/subject for now).
_LEAVE_DOMAIN = "luanar.ac.mw"


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


def send_decision_email(event: ApprovalEvent) -> None:
    """Enqueue + send one decision email; record ``sent``/``failed`` on the outbox."""
    from notifications.models import NotificationOutbox

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

    try:
        send_mail(
            subject=row.subject,
            message=row.body,
            from_email=settings.DEFAULT_FROM_EMAIL or f"no-reply@{_LEAVE_DOMAIN}",
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — consumer-level isolation
        row.mark_failed(str(exc))
        return

    row.mark_sent()


def register_decision_email_consumer() -> None:
    """Attach the email dispatcher to the Unit 16 bus."""
    from workflows.events import register_consumer

    register_consumer(send_decision_email)


class NotificationSeamUnresolvableError(Exception):
    """Raised when an email recipient cannot be resolved from the record."""
