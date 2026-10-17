"""Leave Plan reminder emails (refinement unit 04).

A plan is personal; its only email is a nudge to its owner, so this composer is
deliberately single-recipient and has no consumer bus behind it — the daily job
in :mod:`plans.tasks` calls it directly.

Two kinds exist, and the outbox's ``one_outbox_row_per_plan_kind`` constraint
makes each fire at most once per plan:

* ``plan_reminder`` — sent when the type's ``plan_notice_days`` window opens.
* ``plan_followup`` — sent once, some days later, if the plan is still sitting
  there unconverted. This is the "you said you'd apply, did you mean to?" nudge.

The row is written here and handed to :mod:`notifications.tasks`, which is the
only module that sends mail. Deliveries are therefore retried and recorded in one
place, and a dead relay can never roll back the plan state that produced the mail.
"""

from __future__ import annotations

from .models import NotificationOutbox

#: Outbox ``kind`` values for the plan family.
PLAN_REMINDER = "plan_reminder"
PLAN_FOLLOW_UP = "plan_followup"

#: ``role_label`` — a plan email always concerns the plan's owner.
OWNER = "employee"


def _dates(plan) -> str:
    return f"{plan.planned_start_date} to {plan.planned_end_date}"


def compose_subject(plan, kind: str) -> str:
    if kind == PLAN_FOLLOW_UP:
        return f"LUANAR leave plan — still want to apply for {plan.leave_type.name}?"
    return f"LUANAR leave plan reminder — {plan.leave_type.name} starts {plan.planned_start_date}"


def compose_body(plan, kind: str) -> str:
    lines = [
        f"Leave type: {plan.leave_type.name}",
        f"Planned dates: {_dates(plan)}",
    ]
    if kind == PLAN_FOLLOW_UP:
        lines.insert(
            0,
            "You planned this leave but have not applied for it yet. If your plans "
            "have changed you can ignore or cancel this plan; otherwise log in and "
            "choose Apply Now to turn it into a leave application.",
        )
    else:
        lines.insert(
            0,
            "This is the reminder you asked for: your planned leave is coming up. "
            "Log in and choose Apply Now to turn this plan into a leave application.",
        )
    if plan.notes:
        lines.append(f"Your notes: {plan.notes}")
    return "\n".join(lines) + "\n"


def load_plan(plan_id):
    from plans.models import LeavePlan

    return (
        LeavePlan.objects.select_related("employee", "leave_type")
        .filter(pk=plan_id)
        .first()
    )


def queue_plan_email(plan, kind: str):
    """Record one plan email and hand it to the delivery task.

    Returns ``(row, created)``; ``created`` is False when the kind already fired,
    which is what keeps a re-run of the daily job from doubling a reminder.
    """
    from .tasks import enqueue_delivery

    if plan.employee is None or not plan.employee.email:
        return None, False

    row, created = NotificationOutbox.objects.get_or_create(
        plan_id=plan.pk,
        kind=kind,
        defaults={
            "recipient_email": plan.employee.email,
            "role_label": OWNER,
            "subject": compose_subject(plan, kind),
            "body": compose_body(plan, kind),
        },
    )
    if created:
        enqueue_delivery(row, recipients=[row.recipient_email])
    return row, created
