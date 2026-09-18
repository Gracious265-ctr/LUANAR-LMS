"""Entitlement and leave-rule resolution domain logic for the leave app."""

from datetime import date

from django.utils import timezone
from django.utils.text import slugify

from .models import FinancialYear, GradeEntitlement, LeaveRule, LeaveType, PublicHoliday


def normalize_grade(grade: str) -> str | None:
    """Trim and upper-case a grade for matching; None when blank."""
    value = (grade or "").strip().upper()
    return value or None


def grade_in_range(grade: str, grade_start: str, grade_end: str) -> bool:
    """Return True when a normalized grade falls inside a normalized range."""
    return grade_start <= grade <= grade_end


def ranges_overlap(start: str, end: str, other_start: str, other_end: str) -> bool:
    """Return True when two normalized, inclusive grade ranges overlap."""
    return start <= other_end and other_start <= end


def find_overlapping_rule(
    grade_start: str, grade_end: str, exclude_pk: int | None = None
) -> GradeEntitlement | None:
    """Return an existing rule whose range overlaps the given range, or None.

    Overlap is checked against every rule regardless of ``effective_from``.
    ``exclude_pk`` skips the rule being edited.
    """
    start = normalize_grade(grade_start)
    end = normalize_grade(grade_end)
    if start is None or end is None:
        return None

    queryset = GradeEntitlement.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    for rule in queryset:
        if ranges_overlap(start, end, rule.grade_start, rule.grade_end):
            return rule
    return None


def resolve_grade_entitlement(
    grade: str, as_of: date | None = None
) -> GradeEntitlement | None:
    """Return the effective entitlement rule for a grade on a date, or None.

    Rules with ``effective_from`` on or before ``as_of`` (default: today) whose
    grade range contains the grade are considered; the rule with the latest
    ``effective_from`` wins. Returns ``None`` for blank or unmapped grades.
    """
    key = normalize_grade(grade)
    if key is None:
        return None

    as_of = as_of or timezone.localdate()

    candidates = [
        rule
        for rule in GradeEntitlement.objects.filter(effective_from__lte=as_of)
        if grade_in_range(key, rule.grade_start, rule.grade_end)
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda rule: rule.effective_from)


def normalize_leave_code(value: str) -> str | None:
    """Slugify a leave-type code; None when blank."""
    text = (value or "").strip()
    if not text:
        return None
    return slugify(text)


def resolve_leave_rule(
    leave_type: LeaveType | int, as_of: date | None = None
) -> LeaveRule | None:
    """Return the effective leave rule for a type on a date, or None.

    Rules with ``effective_from`` on or before ``as_of`` (default: today) are
    considered; the rule with the latest ``effective_from`` wins. ``leave_type``
    may be a ``LeaveType`` instance or its primary key.
    """
    as_of = as_of or timezone.localdate()
    return (
        LeaveRule.objects.filter(leave_type=leave_type, effective_from__lte=as_of)
        .order_by("-effective_from")
        .first()
    )


def date_ranges_overlap(
    start: date, end: date, other_start: date, other_end: date
) -> bool:
    """Return True when two inclusive date ranges overlap."""
    return start <= other_end and other_start <= end


def find_overlapping_financial_year(
    start_date: date, end_date: date, exclude_pk: int | None = None
) -> FinancialYear | None:
    """Return an existing financial year overlapping the given range, or None.

    ``exclude_pk`` skips the year being edited.
    """
    queryset = FinancialYear.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    for year in queryset:
        if date_ranges_overlap(start_date, end_date, year.start_date, year.end_date):
            return year
    return None


def financial_year_for_date(d: date) -> FinancialYear | None:
    """Return the configured financial year containing date ``d``, or None.

    Non-overlap makes the match unique; future periods are matched too, which is
    what leave-application validation will use to reject boundary-crossing.
    """
    return (
        FinancialYear.objects.filter(start_date__lte=d, end_date__gte=d)
        .order_by("-start_date")
        .first()
    )


def active_financial_year() -> FinancialYear | None:
    """Return the financial year flagged as active, or None."""
    return FinancialYear.objects.filter(is_active=True).order_by("-start_date").first()


def public_holidays_between(start: date, end: date):
    """Return public holidays on dates in the inclusive range ``[start, end]``.

    This is the configuration boundary later working-day calculations consume.
    """
    return PublicHoliday.objects.filter(date__gte=start, date__lte=end).order_by("date")