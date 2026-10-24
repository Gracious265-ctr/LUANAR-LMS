"""The daily Leave Plan job (refinement unit 04).

One task, three passes, all idempotent so a double run (worker restart, manual
re-trigger) sends nothing twice:

1. **Remind** — an ``upcoming`` plan whose type names a ``notice_days``
   window that has just opened is emailed and moved to ``notified``. The
   window is ``LeaveType.notice_days`` read straight from ``leave_types`` —
   the single number Unit 14's submission validation enforces too.
2. **Follow up** — a ``notified`` plan still unconverted
   :data:`FOLLOW_UP_AFTER_DAYS` days later gets one follow-up, then never again.
3. **Mark missed** — an open plan whose window has passed unmoved becomes
   ``missed`` so the employee's "still open" list stays honest.

The task never touches the approval workflow: converting or applying is always
the employee's own later action.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from notifications.plans import PLAN_FOLLOW_UP, PLAN_REMINDER, queue_plan_email
from notifications.services import create_notification

from .models import LeavePlan, LeavePlanStatus
from .services import mark_missed_plans

#: Days after the reminder before a still-open plan is chased once.
FOLLOW_UP_AFTER_DAYS = 5


def _send_reminders(today) -> int:
    """Email every plan whose notice window just opened; return the count."""
    sent = 0
    plans = LeavePlan.objects.filter(
        status=LeavePlanStatus.UPCOMING,
        planned_start_date__gte=today,
        leave_type__notice_days__isnull=False,
    ).select_related("employee", "leave_type")
    for plan in plans:
        notice = plan.leave_type.notice_days or 0
        if today < plan.planned_start_date - timedelta(days=notice):
            continue
        _, created = queue_plan_email(plan, PLAN_REMINDER)
        if created:
            create_notification(
                recipient=plan.employee,
                event_type="plan.reminder",
                message=(
                    f"Reminder: your planned {plan.leave_type.name} leave "
                    f"starts {plan.planned_start_date}"
                ),
                link=f"/dashboard/plans/{plan.pk}",
            )
        plan.status = LeavePlanStatus.NOTIFIED
        if plan.notified_at is None:
            plan.notified_at = timezone.now()
        plan.save(update_fields=["status", "notified_at", "updated_at"])
        if created:
            sent += 1
    return sent


def _send_follow_ups(today) -> int:
    """Chase notified plans left unconverted; return the count sent."""
    sent = 0
    plans = LeavePlan.objects.filter(
        status=LeavePlanStatus.NOTIFIED,
        planned_start_date__gte=today,
        follow_up_sent_at__isnull=True,
    ).select_related("employee", "leave_type")
    for plan in plans:
        if plan.notified_at is None:
            continue
        due_on = timezone.localtime(plan.notified_at).date() + timedelta(
            days=FOLLOW_UP_AFTER_DAYS
        )
        if today < due_on:
            continue
        _, created = queue_plan_email(plan, PLAN_FOLLOW_UP)
        if created:
            create_notification(
                recipient=plan.employee,
                event_type="plan.follow_up",
                message=(
                    f"You planned {plan.leave_type.name} leave starting "
                    f"{plan.planned_start_date} but have not applied yet"
                ),
                link=f"/dashboard/plans/{plan.pk}",
            )
        plan.follow_up_sent_at = timezone.now()
        plan.save(update_fields=["follow_up_sent_at", "updated_at"])
        if created:
            sent += 1
    return sent


def check_and_notify_plans():
    """Daily entry point. Returns a small dict of what each pass did."""
    today = timezone.localdate()
    reminders = _send_reminders(today)
    follow_ups = _send_follow_ups(today)
    missed = mark_missed_plans(as_of=today)
    return {
        "date": today.isoformat(),
        "reminders": reminders,
        "follow_ups": follow_ups,
        "missed": missed,
    }
