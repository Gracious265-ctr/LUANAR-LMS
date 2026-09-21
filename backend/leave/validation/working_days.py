"""Calendar helpers for leave validation (Unit 14).

Ranges are inclusive on both ends. Weekends are Saturday and Sunday; holidays
come only from the rules provider (there is no substitute-holiday logic here —
that is Unit 5 data). Iteration is day by day, which is fine because ranges are
bounded by the financial year (at most 366 days).
"""

from datetime import date


def is_weekend(d: date) -> bool:
    """Return True when *d* is a Saturday or Sunday."""
    return d.weekday() >= 5


def is_working_day(d: date, holidays: set[date]) -> bool:
    """Return True when *d* is neither a weekend nor a holiday."""
    return not is_weekend(d) and d not in holidays


def count_working_days(start: date, end: date, holidays: set[date]) -> int:
    """Count working days in the inclusive range ``[start, end]``.

    Returns 0 when ``end < start``.
    """
    if end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if is_working_day(current, holidays):
            total += 1
        current = date.fromordinal(current.toordinal() + 1)
    return total


def count_calendar_days(start: date, end: date) -> int:
    """Count calendar days in the inclusive range ``[start, end]`` (0 if reversed)."""
    if end < start:
        return 0
    return (end - start).days + 1


def working_days_elapsed(today: date, start: date, holidays: set[date]) -> int:
    """Count working days in ``[today + 1, start]``, inclusive of ``start``.

    This is the notice-period helper: the working days between today and the
    intended start.
    """
    if start <= today:
        return 0
    return count_working_days(
        date.fromordinal(today.toordinal() + 1), start, holidays
    )