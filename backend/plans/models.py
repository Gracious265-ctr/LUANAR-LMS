"""Leave Plans (refinement unit 04).

A :class:`LeavePlan` is a personal scheduling/reminder tool, not a request: it is
never submitted and never approved. It records an intended leave type and date
range for a financial year, and when the configured notice window arrives the
daily job emails the owner a reminder. At any point the owner can convert the
plan into a *draft* leave application through the existing leave flow — the
plan's job ends the moment the draft exists.
"""

import uuid

from django.conf import settings
from django.db import models


class LeavePlanStatus(models.TextChoices):
    """The plan's lifecycle. ``converted`` is terminal and means "handed off"."""

    UPCOMING = "upcoming", "Upcoming"
    NOTIFIED = "notified", "Notified"
    MISSED = "missed", "Missed"
    CONVERTED = "converted", "Converted"
    CANCELLED = "cancelled", "Cancelled"


class LeavePlan(models.Model):
    """One employee's intended leave for a financial year (never submitted)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_plans",
    )
    leave_type = models.ForeignKey(
        "leave_config.LeaveType",
        on_delete=models.PROTECT,
        related_name="leave_plans",
    )
    financial_year = models.ForeignKey(
        "leave.FinancialYear",
        on_delete=models.PROTECT,
        related_name="leave_plans",
    )
    planned_start_date = models.DateField()
    planned_end_date = models.DateField()
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=LeavePlanStatus.choices,
        default=LeavePlanStatus.UPCOMING,
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    follow_up_sent_at = models.DateTimeField(null=True, blank=True)
    converted_application = models.ForeignKey(
        "leave.LeaveApplication",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["planned_start_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(planned_end_date__gte=models.F("planned_start_date")),
                name="leaveplan_end_date_gte_start_date",
            ),
        ]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["status", "planned_start_date"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.leave_type.name} {self.planned_start_date}–"
            f"{self.planned_end_date} ({self.status})"
        )

    @property
    def is_actionable(self) -> bool:
        """True while the plan can still be converted to a draft."""
        return self.status in (
            LeavePlanStatus.UPCOMING,
            LeavePlanStatus.NOTIFIED,
        )
