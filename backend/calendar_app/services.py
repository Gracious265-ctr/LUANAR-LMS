"""Reading the calendar: working days and resolved holidays (§3.4–3.5).

Every module that needs to know "is this a working day?" or "is this a holiday?"
goes through here rather than querying the models directly, so the observed-shift
and recurrence rules live in exactly one place (§3.8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator

from users.models import User

from .models import Holiday, WorkingDayPattern

__all__ = [
    "DEFAULT_WORKING_WEEKDAYS",
    "ResolvedHoliday",
    "can_access_calendar",
    "get_holidays_for_range",
    "get_working_day_pattern",
    "holidays_map",
    "working_weekdays",
]

#: ``date.weekday()`` indices for the default Mon–Fri week. Used until HR saves
#: an explicit pattern, so an unsaved pattern changes no existing behaviour.
DEFAULT_WORKING_WEEKDAYS = frozenset({0, 1, 2, 3, 4})

#: How far forward an observed holiday may be shifted before giving up. Seven
#: days always contains a working day unless the pattern is empty.
_SHIFT_LIMIT_DAYS = 7


def can_access_calendar(user) -> bool:
    """HR (or anyone administering the system) may write calendar configuration.

    The refinement unit's §2 snippet named an ``HR`` Django group; this
    deployment has no such group — every other launcher and dashboard gate
    checks ``User.Role.HR`` (see ``leave_types.services.can_access_leave_types``)
    — so the role check is used instead (recorded as an adaptation).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return getattr(user, "role", None) == User.Role.HR


@dataclass(frozen=True)
class ResolvedHoliday:
    """A holiday occurrence placed on the date it is actually observed.

    ``date`` is the effective date (after recurrence expansion and observed
    shift); ``holiday`` is the configured row. Two occurrences may share a date
    when a shift lands one on another holiday — callers keyed by date take the
    last, which is why results are sorted.
    """

    date: date
    holiday: Holiday


def get_working_day_pattern() -> WorkingDayPattern | None:
    """The configured pattern row, or ``None`` when HR has never saved one."""
    return WorkingDayPattern.objects.order_by("pk").first()


def working_weekdays(pattern: WorkingDayPattern | None = None) -> set[int]:
    """The working ``date.weekday()`` indices, defaulting to Mon–Fri."""
    if pattern is None:
        pattern = get_working_day_pattern()
    if pattern is None:
        return set(DEFAULT_WORKING_WEEKDAYS)
    return pattern.working_weekdays()


def _shift_to_working_day(value: date, weekdays: set[int]) -> date:
    """The first working day on or after ``value`` (value itself if working)."""
    candidate = value
    for _ in range(_SHIFT_LIMIT_DAYS):
        if candidate.weekday() in weekdays:
            return candidate
        candidate += timedelta(days=1)
    return value


def _occurrences(holiday: Holiday, start: date, end: date) -> Iterator[date]:
    """Yield each date this holiday falls on within ``[start, end]``.

    A one-off holiday yields its single date if it falls in range. A recurring
    one yields its month/day in every year the range spans; a Feb 29 reference
    is skipped in non-leap years rather than raising.
    """
    if not holiday.is_recurring:
        if start <= holiday.date <= end:
            yield holiday.date
        return

    for year in range(start.year, end.year + 1):
        try:
            candidate = date(year, holiday.date.month, holiday.date.day)
        except ValueError:
            continue
        if start <= candidate <= end:
            yield candidate


def get_holidays_for_range(
    start: date, end: date
) -> list[ResolvedHoliday]:
    """Resolve recurring holidays into actual dates in ``[start, end]`` (§3.5).

    Applies ``observed_shift`` so a holiday landing on a non-working day moves
    to the nearest working day. Results are sorted by effective date so a
    date-keyed consumer sees a deterministic choice on a collision.

    ``start``/``end`` are inclusive.
    """
    weekdays = working_weekdays()
    resolved: list[ResolvedHoliday] = []

    for holiday in Holiday.objects.all().select_related("financial_year"):
        for occurrence in _occurrences(holiday, start, end):
            effective = occurrence
            if holiday.observed_shift:
                effective = _shift_to_working_day(occurrence, weekdays)
            if start <= effective <= end:
                resolved.append(ResolvedHoliday(date=effective, holiday=holiday))

    resolved.sort(key=lambda item: (item.date, item.holiday.name, item.holiday.pk))
    return resolved


def holidays_map(start: date, end: date) -> dict[date, str]:
    """Resolved holidays as ``{date: name}`` — the rules-provider shape (§3.8)."""
    return {item.date: item.holiday.name for item in get_holidays_for_range(start, end)}
