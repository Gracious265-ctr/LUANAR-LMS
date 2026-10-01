"""Plan-lifecycle email notifications (Unit 25, D12).

Like :mod:`notifications.services`, each email is one append-only outbox row in
the ``plan`` or ``plan_block`` subject family, deduplicated by a partial unique
constraint so a re-emitted event never sends a second email:

* ``plan``  rows key on ``(plan, kind, submission_cycle, role_label)``
* ``plan_block`` rows key on ``(plan_block, kind, role_label)``

A stage is resolved by whoever acts first, so ``KIND_PLAN_ASSIGNED`` goes to
*every* person in the live stage's eligibility snapshot in one email — one outbox
row per stage, matching how the leave approval bus broadcasts a decision — rather
than guessing which of them should be told.

Delivery failures are recorded on the row by
:func:`notifications.tasks.deliver_notification` and swallowed — one dead mail
relay can never take down a plan decision or a confirmation.
"""

from __future__ import annotations

from leave.providers import get_today
from notifications.models import NotificationOutbox

KIND_PLAN_ASSIGNED = "plan_assigned"
KIND_PLAN_FINALISED = "plan_finalised"
KIND_BLOCK_CONFIRMED = "plan_block_confirmed"
KIND_BLOCK_RELEASED = "plan_block_released"
KIND_BLOCK_REMINDER = "plan_block_confirm_reminder"


def _deliver(*, row_defaults: dict, unique_fields: dict, recipients):
    """Idempotently record one outbox row and queue it for ``recipients``."""
    from notifications.tasks import enqueue_delivery

    unique_fields.setdefault("submission_cycle", 1)
    row, created = NotificationOutbox.objects.get_or_create(
        **unique_fields,
        defaults=row_defaults,
    )
    if not created:
        return
    if not recipients:
        return
    enqueue_delivery(row, recipients=recipients)


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
    """Email everyone entitled to act that a new plan needs a decision.

    Recipients are read from the live stage's eligibility snapshot — the same
    rows the authorisation check uses — with an active delegation swapped for its
    delegate, so somebody away under a delegation is not asked to act and their
    delegate is. ``role_label`` is the stage role, which is what makes one row per
    stage and keeps a re-emitted activation from sending a second email.
    """
    from plans.models import LeaveDayPlan
    from plans.services import acting_approver_ids, eligible_approver_ids

    plan = LeaveDayPlan.objects.select_related("employee").filter(pk=plan_id).first()
    if plan is None or plan.current_stage_id is None:
        return
    stage = plan.current_stage
    if stage is None or stage.status != "pending":
        return

    approver_ids = acting_approver_ids(plan, eligible_approver_ids(plan, stage))
    if not approver_ids:
        return

    from django.contrib.auth import get_user_model

    recipients = [
        email
        for email in get_user_model()
        .objects.filter(pk__in=approver_ids)
        .values_list("email", flat=True)
        if email
    ]
    if not recipients:
        return

    _deliver(
        unique_fields={
            "plan_id": plan.pk,
            "kind": KIND_PLAN_ASSIGNED,
            "submission_cycle": plan.submission_cycle,
            "role_label": stage.role_label[:32] or "approver",
        },
        row_defaults={
            "recipient_email": recipients[0],
            "subject": (
                f"LUANAR leave plan approval — {plan.employee.get_full_name()} "
                f"{plan.period_start} to {plan.period_end}"
            )[:200],
            "body": (
                f"{plan.employee.get_full_name()} submitted a leave day plan.\n"
                f"Period: {plan.period_start} to {plan.period_end}\n"
                f"Financial year: {plan.financial_year_label}\n"
                "Open the plans queue to review and decide."
            ),
        },
        recipients=recipients,
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
            role_label=(
                plan.current_stage.role_label
                if plan.current_stage_id
                else "approver"
            )[:32],
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