"""Plan-lifecycle email notifications (Unit 25, D12).

Like :mod:`notifications.services`, each email is one append-only outbox row in
the ``plan`` or ``plan_block`` subject family, deduplicated by a partial unique
constraint so a re-emitted event never sends a second email:

* ``plan``  rows key on ``(plan, kind, submission_cycle, role_label)``
* ``plan_block`` rows key on ``(plan_block, kind, role_label)``

Send failures are recorded on the row and swallowed — one dead email backend
can never take down a plan decision or a confirmation.
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail

from leave.providers import get_today
from notifications.models import NotificationOutbox
from notifications.services import LEAVE_DOMAIN

KIND_PLAN_ASSIGNED = "plan_assigned"
KIND_PLAN_FINALISED = "plan_finalised"
KIND_BLOCK_CONFIRMED = "plan_block_confirmed"
KIND_BLOCK_RELEASED = "plan_block_released"
KIND_BLOCK_REMINDER = "plan_block_confirm_reminder"


def _deliver(*, row_defaults: dict, unique_fields: dict, recipients):
    """Idempotently create and deliver one outbox row to ``recipients``."""
    unique_fields.setdefault("submission_cycle", 1)
    row, created = NotificationOutbox.objects.get_or_create(
        **unique_fields,
        defaults=row_defaults,
    )
    if not created:
        return
    try:
        send_mail(
            subject=row.subject,
            message=row.body,
            from_email=settings.DEFAULT_FROM_EMAIL or f"no-reply@{LEAVE_DOMAIN}",
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — consumer-level isolation
        row.mark_failed(str(exc))
        return
    row.mark_sent()


def _plan_row(plan, *, kind, role_label, subject, body, recipient):
    _deliver(
        unique_fields={
            "plan_id": plan.pk,
            "kind": kind,
            "submission_cycle": plan.submission_cycle,
            "role_label": role_label,
        },
        row_defaults={
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
        },
        recipients=[recipient],
    )


def _block_row(block, plan, *, kind, role_label, subject, body, recipient):
    _deliver(
        unique_fields={
            "plan_block_id": block.pk,
            "kind": kind,
            "role_label": role_label,
        },
        row_defaults={
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
        },
        recipients=[recipient],
    )


def notify_plan_assigned(plan_id) -> None:
    """Email the current approver that a new plan needs their decision."""
    from plans.models import LeaveDayPlan

    plan = LeaveDayPlan.objects.select_related(
        "employee", "current_approver"
    ).filter(pk=plan_id).first()
    if plan is None or plan.current_approver_id is None:
        return
    approver = plan.current_approver
    if not approver.email:
        return
    stage = plan.current_stage
    _plan_row(
        plan,
        kind=KIND_PLAN_ASSIGNED,
        role_label=(stage.role_label if stage else "approver")[:32],
        subject=(
            f"LUANAR leave plan approval — {plan.employee.get_full_name()} "
            f"{plan.period_start} to {plan.period_end}"
        )[:200],
        body=(
            f"{plan.employee.get_full_name()} submitted a leave day plan.\n"
            f"Period: {plan.period_start} to {plan.period_end}\n"
            f"Financial year: {plan.financial_year_label}\n"
            "Open the plans queue to review and decide."
        ),
        recipient=approver.email,
    )


def notify_plan_decided(plan_id, finalised: bool) -> None:
    """Email the plan owner (and the finalising approver) the outcome."""
    from plans.models import LeaveDayPlan

    plan = LeaveDayPlan.objects.select_related("employee").filter(pk=plan_id).first()
    if plan is None or plan.employee_id is None or not plan.employee.email:
        return
    outcome = "approved" if finalised else "rejected"
    _plan_row(
        plan,
        kind=KIND_PLAN_FINALISED,
        role_label="owner",
        subject=(
            f"LUANAR leave plan {outcome} — {plan.period_start} to {plan.period_end}"
        )[:200],
        body=(
            f"Your leave day plan for {plan.period_start} to {plan.period_end} "
            f"was {outcome}.\n"
            "Open the plans page to review the details."
        ),
        recipient=plan.employee.email,
    )
    if finalised and plan.current_approver_id and plan.current_approver.email:
        _plan_row(
            plan,
            kind=KIND_PLAN_FINALISED,
            role_label=(plan.current_stage.role_label if plan.current_stage_id else "approver")[:32],
            subject=(
                f"LUANAR leave plan approved — {plan.employee.get_full_name()}"
            )[:200],
            body=(
                f"The leave day plan of {plan.employee.get_full_name()} "
                f"({plan.period_start} to {plan.period_end}) was approved and "
                "the days are now reserved."
            ),
            recipient=plan.current_approver.email,
        )


def notify_plan_block_confirmed(block_id, plan_id) -> None:
    """Email the owner once a reserved block is confirmed and locked."""
    from plans.models import LeaveDayPlan, LeavePlanBlock

    block = (
        LeavePlanBlock.objects.select_related("plan__employee")
        .filter(pk=block_id, plan_id=plan_id)
        .first()
    )
    if block is None or not block.plan.employee.email:
        return
    _block_row(
        block,
        block.plan,
        kind=KIND_BLOCK_CONFIRMED,
        role_label="owner",
        subject=(
            f"Plan block confirmed — {block.start_date} to {block.end_date}"
        )[:200],
        body=(
            f"Your planned leave {block.start_date} to {block.end_date} "
            "is confirmed; the reserved days are locked for you.\n"
            "Submit a leave application for these dates to proceed."
        ),
        recipient=block.plan.employee.email,
    )


def notify_plan_block_released(block_id, plan_id) -> None:
    """Email the owner when a reserved block is released (declined or lapsed)."""
    from plans.models import LeaveDayPlan, LeavePlanBlock

    block = (
        LeavePlanBlock.objects.select_related("plan__employee")
        .filter(pk=block_id, plan_id=plan_id)
        .first()
    )
    if block is None or not block.plan.employee.email:
        return
    _block_row(
        block,
        block.plan,
        kind=KIND_BLOCK_RELEASED,
        role_label="owner",
        subject=(
            f"Plan block released — {block.start_date} to {block.end_date}"
        )[:200],
        body=(
            f"The planned leave {block.start_date} to {block.end_date} was "
            "released; the reserved days are available again."
        ),
        recipient=block.plan.employee.email,
    )


def send_plan_block_confirmation_reminders() -> int:
    """Email employees whose reserved blocks entered their confirmation window.

    Idempotent: each block gets at most one reminder row, so repeated daily
    runs never resend. Returns the number of reminders created (sent or failed).
    """
    from plans.models import LeaveDayPlan, LeavePlanBlock
    from plans.services import _confirmation_window_start

    today = get_today()
    due = LeavePlanBlock.objects.filter(
        plan__status=LeaveDayPlan.Status.APPROVED,
        status=LeavePlanBlock.Status.RESERVED,
        start_date__gt=today,
    ).select_related("plan__employee")

    sent = 0
    for block in due:
        window_start = _confirmation_window_start(block)
        days_left = (block.start_date - today).days
        if window_start > today:
            continue  # not yet in the confirmation window
        if not block.plan.employee.email:
            continue
        existed = NotificationOutbox.objects.filter(
            plan_block_id=block.pk,
            kind=KIND_BLOCK_REMINDER,
            role_label="owner",
        ).exists()
        if existed:
            continue
        _block_row(
            block,
            block.plan,
            kind=KIND_BLOCK_REMINDER,
            role_label="owner",
            subject=(
                f"Confirm your planned leave — {block.start_date} to {block.end_date}"
            )[:200],
            body=(
                f"Your reserved leave {block.start_date} to {block.end_date} "
                f"starts in {days_left} day(s).\n"
                "Confirm it now so the days stay locked for you, or release "
                "it so they become available again."
            ),
            recipient=block.plan.employee.email,
        )
        sent += 1
    return sent