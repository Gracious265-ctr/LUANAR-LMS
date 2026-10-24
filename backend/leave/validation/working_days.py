"""Calendar helpers for leave validation (Unit 14).

Ranges are inclusive on both ends. Which weekdays count as working days comes
from the Calendar app's working-day pattern (§3.4, refinement unit 07): the
``weekdays`` parameters are the ``date.weekday()`` indices that count, and when
omitted the Mon–Fri default applies — so pure helpers never touch the database
and only the pipeline passes the configured pattern in. Holidays come only from
the rules provider (there is no substitute-holiday logic here — that is the
Calendar app's ``observed_shift`` data). Iteration is day by day, which is fine
because ranges are bounded by the financial year (at most 366 days).
"""

from datetime import date

from calendar_app.services import DEFAULT_WORKING_WEEKDAYS


def configured_weekdays() -> set[int]:
    """The Calendar app's configured working weekdays (Mon–Fri until saved)."""
    from calendar_app.services import working_weekdays

    return working_weekdays()


def is_weekend(d: date, weekdays: set[int] | None = None) -> bool:
    """Return True when *d* is not one of the working weekdays.

    Defaults to the Mon–Fri week; pass the configured pattern (via
    :func:`configured_weekdays`) to honour an HR-defined working week.
    """
    if weekdays is None:
        weekdays = DEFAULT_WORKING_WEEKDAYS
    return d.weekday() not in weekdays


def is_working_day(
    d: date, holidays: set[date], weekdays: set[int] | None = None
) -> bool:
    """Return True when *d* is a working weekday and not a holiday."""
    return not is_weekend(d, weekdays) and d not in holidays


def count_working_days(
    start: date,
    end: date,
    holidays: set[date],
    weekdays: set[int] | None = None,
) -> int:
    """Count working days in the inclusive range ``[start, end]``.

    Returns 0 when ``end < start``.
    """
    if end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if is_working_day(current, holidays, weekdays):
            total += 1
        current = date.fromordinal(current.toordinal() + 1)
    return total


def count_calendar_days(start: date, end: date) -> int:
    """Count calendar days in the inclusive range ``[start, end]`` (0 if reversed)."""
    if end < start:
        return 0
    return (end - start).days + 1


def working_days_elapsed(
    today: date,
    start: date,
    holidays: set[date],
    weekdays: set[int] | None = None,
) -> int:
    """Count working days in ``[today + 1, start]``, inclusive of ``start``.

    This is the notice-period helper: the working days between today and the
    intended start.
    """
    if start <= today:
        return 0
    return count_working_days(
        date.fromordinal(today.toordinal() + 1), start, holidays, weekdays
    )
