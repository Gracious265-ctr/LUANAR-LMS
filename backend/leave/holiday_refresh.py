"""Recompute stored draft day counts when the holiday calendar changes.

``LeaveApplication.calculated_days`` is denormalized: it is written when a draft
is created or edited, so it is only as fresh as the last edit. That is fine until
HR changes the calendar — a new holiday, a moved holiday, a deleted holiday, or a
change to which weekdays count as working days — which changes the answer for
dates the employee already chose without touching their draft. The employee's
screen would keep showing the pre-change number until they happened to re-save.

So a calendar change refreshes the drafts it can possibly affect. Submitted and
approved applications are deliberately left alone: their count was frozen at
submission (architecture invariant 12.5) and their ledger already moved.
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from calendar_app.models import Holiday, WorkingDayPattern

from .models import LeaveApplication

#: Statuses whose ``calculated_days`` is a live preview rather than history.
#: Mirrors ``LeaveApplicationViewSet.EDITABLE_STATUSES``.
LIVE_PREVIEW_STATUSES = (
    LeaveApplication.Status.DRAFT,
    LeaveApplication.Status.REJECTED,
)


def refresh_drafts_covering(*dates) -> None:
    """Re-count every live draft whose range covers any of ``dates``.

    A queryset update rather than ``save()``: this is a derived column, and
    ``LeaveApplication.save`` carries signals the employee's own edits own.
    ``None``/empty dates are ignored so a delete of a dateless row is a no-op.
    """
    affected = [value for value in dates if value]
    if not affected:
        return

    from .services.working_days import calculate_working_days

    candidates = LeaveApplication.objects.filter(
        status__in=LIVE_PREVIEW_STATUSES,
        start_date__isnull=False,
        end_date__isnull=False,
        end_date__gte=min(affected),
        start_date__lte=max(affected),
    ).only("id", "start_date", "end_date", "calculated_days")

    for application in candidates:
        correct = calculate_working_days(application.start_date, application.end_date)
        if correct != application.calculated_days:
            LeaveApplication.objects.filter(pk=application.pk).update(
                calculated_days=correct
            )


def refresh_all_live_drafts() -> None:
    """Re-count every live draft — used when the working-day pattern changes."""
    from .services.working_days import calculate_working_days

    candidates = LeaveApplication.objects.filter(
        status__in=LIVE_PREVIEW_STATUSES,
        start_date__isnull=False,
        end_date__isnull=False,
    ).only("id", "start_date", "end_date", "calculated_days")

    for application in candidates:
        correct = calculate_working_days(application.start_date, application.end_date)
        if correct != application.calculated_days:
            LeaveApplication.objects.filter(pk=application.pk).update(
                calculated_days=correct
            )


@receiver(pre_save, sender=Holiday)
def remember_previous_holiday_date(sender, instance, **kwargs):
    """Stash the old date so a moved holiday also repairs the range it left."""
    if not instance.pk:
        instance._previous_date = None
        return
    instance._previous_date = (
        sender.objects.filter(pk=instance.pk)
        .values_list("date", flat=True)
        .first()
    )


@receiver(post_save, sender=Holiday)
def refresh_draft_day_counts(sender, instance, created, **kwargs):
    """Re-count the drafts whose range covers this holiday's old or new date."""
    refresh_drafts_covering(
        getattr(instance, "_previous_date", None),
        instance.date,
    )


@receiver(post_delete, sender=Holiday)
def refresh_draft_day_counts_after_delete(sender, instance, **kwargs):
    """A deleted holiday makes its date 'working' again for affected drafts."""
    refresh_drafts_covering(instance.date)


@receiver(post_save, sender=WorkingDayPattern)
def refresh_draft_day_counts_after_pattern_change(sender, instance, created, **kwargs):
    """A changed week affects every draft, so re-count them all."""
    refresh_all_live_drafts()
