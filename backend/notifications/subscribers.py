"""Event subscribers that turn domain events into emails (Unit 22).

Each ``on_*`` handler reads only the correlated application/request rows needed
to compose the template context (no business logic is re-run), renders the
event's registered template and enqueues one :class:`Notification` per
eligible recipient. ``on_domain_event`` is the settings-resolved entry point;
``leave_application_submitted`` is connected as a Django signal receiver in
``apps.py``.
"""

from leave.models import LeaveApplication, LeaveType
from users.models import User
from workflows.models import ApplicationStage

from . import templates
from .services import send_notification


def on_domain_event(kind: str, event) -> None:
    """Dispatch handled in :mod:`notifications.dispatcher`."""
    handler = _HANDLERS.get(kind)
    if handler is not None:
        handler(event)
    return None


def on_application_submitted(sender, application, **_) -> None:
    """Receiver for ``leave_application_submitted`` (Unit 14 seam)."""
    from workflows.providers import get_workflow_provider

    provider = get_workflow_provider()
    member_ids = provider.get_workflow_member_user_ids(application)
    recipients = _users_for(set([application.employee_id, *member_ids]))

    rendered = templates.render(
        "leave.application.submitted", _application_context(application)
    )
    send_notification(
        event_type="leave.application.submitted",
        recipients=recipients,
        subject=rendered.subject,
        body=rendered.body,
        application_id=application.id,
    )


def on_approval_event(event) -> None:
    """Subscriber for :class:`workflows.events.ApprovalEvent`."""
    application = (
        LeaveApplication.objects.select_related("employee")
        .filter(pk=event.application_id)
        .first()
    )
    if application is None:
        return None

    context = _application_context(application)
    context["status"] = event.payload.get("status") or application.status

    if event.kind == "stage_assigned":
        stage = (
            ApplicationStage.objects.select_related("assigned_approver")
            .filter(
                application=application,
                status=ApplicationStage.Status.PENDING,
            )
            .first()
        )
        if stage is None:
            return None
        context["stage"] = stage.role_label
        rendered = templates.render("approval.stage_assigned", context)
        send_notification(
            event_type="approval.stage_assigned",
            recipients=[stage.assigned_approver],
            subject=rendered.subject,
            body=rendered.body,
            application_id=application.id,
        )
        return None

    if event.kind == "decision_recorded":
        context.update(
            {
                "action": event.action,
                "approver": event.payload.get("approver", ""),
                "comment": event.payload.get("comment", ""),
            }
        )
        rendered = templates.render("approval.decision_recorded", context)
        next_approver = _pending_approver(application)
        recipients = [application.employee]
        if next_approver is not None:
            recipients.append(next_approver)
        send_notification(
            event_type="approval.decision_recorded",
            recipients=recipients,
            subject=rendered.subject,
            body=rendered.body,
            application_id=application.id,
        )
        return None

    # application_finalised
    rendered = templates.render("approval.application_finalised", context)
    send_notification(
        event_type="approval.application_finalised",
        recipients=[application.employee],
        subject=rendered.subject,
        body=rendered.body,
        application_id=application.id,
    )
    return None


def on_cancellation_event(event) -> None:
    """Subscriber for :class:`leave.cancellations.events.CancellationEvent`."""
    from leave.cancellations.events import set_notification_state

    application = (
        LeaveApplication.objects.select_related("employee")
        .filter(pk=event.application_id)
        .first()
    )
    if application is None:
        return None

    employee_user_id = application.employee_id
    recipient_ids = set(event.recipient_user_ids)
    recipients = _users_for(recipient_ids)
    recipient_by_user_id = {user.pk: user for user in recipients}
    employee_pk = employee_user_id if employee_user_id in recipient_ids else None

    context = _application_context(application)
    context.update(event.payload)
    context.setdefault("stage_order", event.payload.get("stage_order", ""))
    rendered = templates.render(event.event_name, context)

    def flip_employee_state(rows):
        if employee_pk is None:
            return
        state = "sent" if any(row.recipient_id == employee_pk for row in rows) else "failed"
        set_notification_state(event.request_id, state)

    send_notification(
        event_type=event.event_name,
        recipients=list(recipient_by_user_id.values()),
        subject=rendered.subject,
        body=rendered.body,
        application_id=event.application_id,
        send_sync_callbacks=(flip_employee_state,),
    )
    return None


def on_delegation_event(event) -> None:
    """Subscriber for :class:`workflows.events.DelegationEvent`."""
    from workflows.models import Delegation

    delegation = Delegation.objects.select_related(
        "approver", "delegate", "requested_by"
    ).filter(pk=event.delegation_id).first()
    if delegation is None:
        return None

    recipient_ids = {event.approver_user_id}
    if event.delegate_user_id is not None:
        recipient_ids.add(event.delegate_user_id)

    context = {
        "approver": _person(delegation.approver),
        "delegate": _person(delegation.delegate) if delegation.delegate else "(unassigned)",
        "dates": _delegation_dates(delegation),
        "decision_reason": delegation.decision_reason,
    }
    rendered = templates.render(event.event_name, context)
    send_notification(
        event_type=event.event_name,
        recipients=_users_for(recipient_ids),
        subject=rendered.subject,
        body=rendered.body,
    )
    return None


def on_reassignment_event(event) -> None:
    """Subscriber for :class:`workflows.events.ReassignmentEvent`."""
    from workflows.models import Reassignment

    reassignment = (
        Reassignment.objects.select_related("to_approver", "from_approver")
        .filter(pk=event.reassignment_id)
        .first()
    )
    application = (
        LeaveApplication.objects.select_related("employee")
        .filter(pk=event.application_id)
        .first()
    )
    if reassignment is None or application is None:
        return None

    context = _application_context(application)
    context.update(
        {
            "to_approver": _person(reassignment.to_approver),
            "from_approver": (
                _person(reassignment.from_approver) if reassignment.from_approver else "(unassigned)"
            ),
            "reason": reassignment.reason,
        }
    )
    rendered = templates.render("reassignment.created", context)
    send_notification(
        event_type="reassignment.created",
        recipients=_users_for({event.to_approver_user_id, event.employee_user_id}),
        subject=rendered.subject,
        body=rendered.body,
        application_id=application.id,
    )
    return None


_HANDLERS = {
    "approval": on_approval_event,
    "cancellation": on_cancellation_event,
    "delegation": on_delegation_event,
    "reassignment": on_reassignment_event,
}


# --- context helpers -------------------------------------------------------------

def _application_context(application) -> dict:
    return {
        "applicant": _person(application.employee),
        "reference_number": application.reference_number or "",
        "leave_type": _leave_type_name(application),
        "dates": _date_range(application),
    }


def _leave_type_name(application) -> str:
    if application.leave_type_id is None:
        return "leave"
    name = (
        LeaveType.objects.filter(pk=application.leave_type_id)
        .values_list("name", flat=True)
        .first()
    )
    return name or "leave"


def _date_range(application) -> str:
    if application.start_date is None and application.end_date is None:
        return ""
    if application.start_date == application.end_date:
        return f"On {application.start_date:%d %b %Y}"
    return (
        f"{application.start_date:%d %b %Y} to {application.end_date:%d %b %Y}"
    )


def _delegation_dates(delegation) -> str:
    if delegation.starts_on is None:
        return ""
    if delegation.ends_on is None:
        return f"from {delegation.starts_on:%d %b %Y} (open-ended)"
    return (
        f"{delegation.starts_on:%d %b %Y} to {delegation.ends_on:%d %b %Y}"
    )


def _person(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.username or ""


def _users_for(user_ids) -> list:
    return list(User.objects.filter(pk__in=set(user_ids)))


def _pending_approver(application):
    stage = (
        ApplicationStage.objects.select_related("assigned_approver")
        .filter(application=application, status=ApplicationStage.Status.PENDING)
        .first()
    )
    return stage.assigned_approver if stage is not None else None