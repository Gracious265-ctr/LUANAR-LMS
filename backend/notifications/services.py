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

from chains.events import APPLICATION_FINALISED, ApprovalEvent

from .models import Notification

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
    from chains.events import register_consumer

    register_consumer(queue_decision_email)


class NotificationSeamUnresolvableError(Exception):
    """Raised when an email recipient cannot be resolved from the record."""


# ---------------------------------------------------------------------------
# In-app notifications (refinement unit 08).
#
# The module-level seam every source module calls instead of inventing its own
# feed. Notifications are personal rows scoped to their recipient, so every
# read/mutation below is filtered by recipient and can never touch another
# user's feed — the same ownership discipline as every other personal-data
# endpoint in the project.
# ---------------------------------------------------------------------------


def create_notification(recipient, event_type: str, message: str, link: str) -> Notification:
    """Persist one in-app notification for ``recipient``."""
    return Notification.objects.create(
        recipient=recipient, event_type=event_type, message=message, link=link
    )


def get_recent_notifications(user, limit=15, unread_only: bool = False) -> list[Notification]:
    """The most recent notifications for the popover, newest first."""
    queryset = Notification.objects.filter(recipient=user)
    if unread_only:
        queryset = queryset.filter(is_read=False)
    return list(queryset.order_by("-created_at")[:limit])


def get_unread_count(user) -> int:
    """The badge count for the navbar bell."""
    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_read(notification_id: str, user) -> None:
    """Mark one of the user's notifications read; another user's id is a no-op."""
    Notification.objects.filter(id=notification_id, recipient=user).update(is_read=True)


def mark_all_read(user) -> None:
    """Clear the requesting user's unread feed."""
    Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)


#: ``ApprovalDecision.Action`` → the in-app ``event_type`` suffix vocabulary.
_DECISION_EVENT_SUFFIXES = {
    "approve": "approved",
    "reject": "rejected",
    "return_for_correction": "correction_required",
}


def queue_decision_notification(event: ApprovalEvent) -> None:
    """In-app feed row for the employee when their application reaches a
    terminal outcome (refinement unit 08 §2.1).

    Registered on the same Unit 16 bus as the email consumer, so it runs on
    commit and only once the decision is durable. An *intermediate* approve is
    deliberately silent — the employee's application is not "approved" until the
    chain finalises (``APPLICATION_FINALISED``); reject and
    return-for-correction are terminal the moment they are recorded. The next
    stage's approvers are notified at the point the stage is opened, not here.
    """
    from approvals.models import ApprovalDecision

    if event.action == ApprovalDecision.Action.APPROVE:
        if event.kind != APPLICATION_FINALISED:
            return
        outcome = "was approved"
    elif event.action == ApprovalDecision.Action.REJECT:
        outcome = "was rejected"
    else:
        outcome = "needs correction"

    employee = _application_employee(event.application_id)
    if employee is None:
        return
    create_notification(
        recipient=employee,
        event_type=f"application.{_DECISION_EVENT_SUFFIXES[event.action]}",
        message=_decision_message(event.application_id, outcome),
        link=f"/applications/{event.application_id}",
    )


def _decision_message(application_id: str, outcome: str) -> str:
    """Short human-readable line, e.g. 'Your Annual leave application was approved'."""
    return f"Your {_application_leave_type_name(application_id)} application {outcome}"


def _application_employee(application_id: str):
    from leave.models import LeaveApplication

    application = LeaveApplication.objects.filter(pk=application_id).only("employee_id").first()
    return application.employee if application is not None else None


def _application_leave_type_name(application_id: str) -> str:
    """Leave type name resolved through the soft ``leave_type_id`` reference."""
    from leave.models import LeaveApplication
    from leave_types.models import LeaveType

    leave_type_id = (
        LeaveApplication.objects.filter(pk=application_id)
        .values_list("leave_type_id", flat=True)
        .first()
    )
    if leave_type_id is None:
        return "leave"
    return (
        LeaveType.objects.filter(pk=leave_type_id)
        .values_list("name", flat=True)
        .first()
        or "leave"
    )


def register_decision_notification_consumer() -> None:
    """Attach the in-app feed to the Unit 16 bus."""
    from chains.events import register_consumer

    register_consumer(queue_decision_notification)
