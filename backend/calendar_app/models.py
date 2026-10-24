"""The institution-wide calendar configuration (refinement unit 07).

Three concepts live here:

- :class:`WorkingDayPattern` — which weekdays count as working days. One row,
  institution-wide (the spec invites a flag if a campus ever needs a different
  week; none does today, so there is a single shared pattern).
- :class:`Holiday` — a public/institutional holiday, recurring or one-off,
  optionally observed-shifted when it lands on a non-working day.
- :class:`CalendarEvent` — an informational institutional entry (graduation,
  orientation week) that may be promoted later to affect leave calculation.

``FinancialYear`` is deliberately *not* re-defined here: it already lives in
``leave`` and is the subject of ``GradeLeaveEntitlement``/``LeavePlan`` foreign
keys, so this app owns its API surface rather than the row.
"""

from django.db import models

#: The pattern's boolean fields in ``date.weekday()`` order (Monday=0 … Sunday=6).
WEEKDAY_FIELDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


class WorkingDayPattern(models.Model):
    """Which weekdays count as working days, institution-wide.

    A single row by convention; ``get_working_day_pattern`` reads the first and
    an absent row means the Mon–Fri default (:data:`DEFAULT_WORKING_WEEKDAYS`),
    so a fresh deployment behaves exactly as the pre-calendar code did.
    """

    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Working-day pattern"
        verbose_name_plural = "Working-day pattern"

    def __str__(self) -> str:
        return "Working-day pattern"

    def working_weekdays(self) -> set[int]:
        """The ``date.weekday()`` indices this pattern treats as working days."""
        return {
            index
            for index, field in enumerate(WEEKDAY_FIELDS)
            if getattr(self, field)
        }


class Holiday(models.Model):
    """A public or institutional holiday.

    For a one-off holiday ``date`` is the holiday itself; for a recurring one it
    is the reference date whose month/day repeats every year. ``financial_year``
    is informational scoping (``null`` means institution-wide) — the leave rules
    resolve holidays by the date range they are asked about, not by this field.
    """

    name = models.CharField(max_length=200)
    date = models.DateField(
        help_text=(
            "The one-off date, or the reference date for a recurring holiday."
        )
    )
    is_recurring = models.BooleanField(
        default=True,
        help_text="Repeats on the same month/day every year.",
    )
    observed_shift = models.BooleanField(
        default=True,
        help_text=(
            "If it falls on a non-working day, shift to the nearest working day."
        ),
    )
    financial_year = models.ForeignKey(
        "leave.FinancialYear",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="holidays",
        help_text="Null when the holiday is institution-wide rather than FY-scoped.",
    )

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "financial_year"],
                name="holiday_date_financial_year_unique",
            ),
        ]

    def __str__(self) -> str:
        scope = " (recurring)" if self.is_recurring else ""
        return f"{self.name} ({self.date}){scope}"


class CalendarEvent(models.Model):
    """An informational institutional calendar entry.

    ``affects_leave_calculation`` defaults to ``False`` so an event is purely
    informational; it exists so graduation week can be promoted to warn/block
    leave without a separate blackout-period model (§3.6).
    """

    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    affects_leave_calculation = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="calendarevent_end_date_gte_start_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.start_date} – {self.end_date})"
