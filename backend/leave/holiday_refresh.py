"""Recompute stored draft day counts when the holiday calendar changes.

``LeaveApplication.calculated_days`` is denormalized: it is written when a draft
is created or edited, so it is only as fresh as the last edit. That is fine until
HR configures a public holiday, which changes the answer for dates the employee
already chose without touching their draft. The employee's screen would keep
showing the pre-holiday number until they happened to re-save.

So a holiday change refreshes the drafts it can possibly affect. Submitted and
approved applications are deliberately left alone: their count was frozen at
submission (architecture invariant 12.5) and their ledger already moved.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import LeaveApplication, PublicHoliday

#: Statuses whose ``calculated_days`` is a live preview rather than history.
#: Mirrors ``LeaveApplicationViewSet.EDITABLE_STATUSES``.
LIVE_PREVIEW_STATUSES = (
    LeaveApplication.Status.DRAFT,
    LeaveApplication.Status.REJECTED,
)


@receiver(pre_save, sender=PublicHoliday)
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


@receiver(post_save, sender=PublicHoliday)
def refresh_draft_day_counts(sender, instance, created, **kwargs):
    """Re-count the drafts whose range covers this holiday's old or new date."""
    from .services.working_days import calculate_working_days

    affected_dates = [
        d for d in (getattr(instance, "_previous_date", None), instance.date) if d
    ]
    if not affected_dates:
        return

    candidates = LeaveApplication.objects.filter(
        status__in=LIVE_PREVIEW_STATUSES,
        start_date__isnull=False,
        end_date__isnull=False,
        end_date__gte=min(affected_dates),
        start_date__lte=max(affected_dates),
    ).only("id", "start_date", "end_date", "calculated_days")

    # A queryset update rather than ``save()``: this is a derived column, and
    # ``LeaveApplication.save`` carries signals the employee's own edits own.
    for application in candidates:
        correct = calculate_working_days(application.start_date, application.end_date)
        if correct != application.calculated_days:
            LeaveApplication.objects.filter(pk=application.pk).update(
                calculated_days=correct
            )
