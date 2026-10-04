"""Entitlement and leave-rule resolution domain logic for the leave app."""

from datetime import date

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.text import slugify

from ..models import FinancialYear, GradeEntitlement, LeaveRule, LeaveType, PublicHoliday


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
    grade_start: str,
    grade_end: str,
    leave_type: LeaveType | int | None = None,
    exclude_pk: int | None = None,
) -> GradeEntitlement | None:
    """Return an existing rule whose range overlaps the given range, or None.

    Overlap is scoped to one leave type. HR must be able to grant a band more
    than one type -- "grade A–C gets 21 days annual *and* 5 compassionate" is two
    rows on the same band -- so a global overlap ban would leave an employee's
    whole entitlement limited to a single type. Within one type a range may still
    only be granted once, which is what ``exclude_pk`` exists for.

    ``leave_type=None`` means "the untyped band", not "any": an untyped row is the
    historical annual-leave entitlement and must not collide with a typed row for
    a different type, or every first typed band would be refused.

    Checked against every rule regardless of ``effective_from``.
    """
    start = normalize_grade(grade_start)
    end = normalize_grade(grade_end)
    if start is None or end is None:
        return None

    queryset = GradeEntitlement.objects.all()
    if leave_type is None:
        queryset = queryset.filter(leave_type__isnull=True)
    else:
        queryset = queryset.filter(leave_type=leave_type)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    for rule in queryset:
        if ranges_overlap(start, end, rule.grade_start, rule.grade_end):
            return rule
    return None


def _covering_rules(
    grade: str, as_of: date, leave_type: LeaveType | int | None
) -> list[GradeEntitlement]:
    """Effective rules covering ``grade``, narrowed to ``leave_type`` if given."""
    queryset = GradeEntitlement.objects.filter(effective_from__lte=as_of)
    if leave_type is not None:
        queryset = queryset.filter(leave_type=leave_type)
    return [
        rule
        for rule in queryset
        if grade_in_range(grade, rule.grade_start, rule.grade_end)
    ]


def resolve_grade_entitlement(
    grade: str,
    as_of: date | None = None,
    leave_type: LeaveType | int | None = None,
) -> GradeEntitlement | None:
    """Return the effective entitlement rule for a grade on a date, or None.

    Rules with ``effective_from`` on or before ``as_of`` (default: today) whose
    grade range contains the grade are considered; the rule with the latest
    ``effective_from`` wins. Returns ``None`` for blank or unmapped grades.

    ``leave_type`` narrows to one type, which matters now that a grade can be
    granted several: "what does grade G get for maternity" is a different answer
    from "what does grade G get". ``None`` means any type, and is only
    unambiguous while a grade has at most one band -- prefer
    :func:`resolve_annual_balance_entitlement` for the balance.
    """
    key = normalize_grade(grade)
    if key is None:
        return None

    as_of = as_of or timezone.localdate()

    candidates = _covering_rules(key, as_of, leave_type)
    if not candidates:
        return None

    return max(candidates, key=lambda rule: rule.effective_from)


def resolve_annual_balance_entitlement(
    grade: str | None, as_of: date | None = None
) -> GradeEntitlement | None:
    """Return the entitlement that funds the annual leave balance for a grade.

    The balance is one number per employee per financial year, not one per leave
    type -- ``LeaveBalanceTransaction`` is annual-scoped -- so the row that funds
    it is the one whose leave type actually consumes annual entitlement. Where no
    band names such a type, the untyped band is used, which is what a row created
    before ``GradeEntitlement.leave_type`` existed means.

    If HR marks two leave types as consuming annual entitlement on one grade, the
    later ``effective_from`` wins. That is a configuration ambiguity rather than a
    supported shape, and it is cheaper to document than to add a second ledger.
    """
    key = normalize_grade(grade)
    if key is None:
        return None

    as_of = as_of or timezone.localdate()
    candidates = _covering_rules(key, as_of, None)
    if not candidates:
        return None

    annual_type_ids = set(
        LeaveRule.objects.filter(
            effective_from__lte=as_of,
            consumes_annual_entitlement=True,
        ).values_list("leave_type_id", flat=True)
    )
    annual = [rule for rule in candidates if rule.leave_type_id in annual_type_ids]
    if annual:
        return max(annual, key=lambda rule: rule.effective_from)

    untyped = [rule for rule in candidates if rule.leave_type_id is None]
    if not untyped:
        return None
    return max(untyped, key=lambda rule: rule.effective_from)


def resolved_annual_entitlement(
    grade: str | None, as_of: date | None = None
) -> GradeEntitlement | None:
    """Resolve a grade to the annual-leave-days entitlement rule (or None)."""
    if not grade:
        return None
    return resolve_annual_balance_entitlement(grade, as_of)



def leave_types_available_to(
    grade: str | None, as_of: date | None = None
) -> QuerySet[LeaveType]:
    """Active leave types a grade is granted, by an effective band."""
    key = normalize_grade(grade)
    if key is None:
        return LeaveType.objects.none()

    as_of = as_of or timezone.localdate()
    granted_ids = {
        rule.leave_type_id
        for rule in GradeEntitlement.objects.filter(
            leave_type_id__isnull=False, effective_from__lte=as_of
        )
        if grade_in_range(key, rule.grade_start, rule.grade_end)
    }
    granted_ids.discard(None)
    return LeaveType.objects.filter(is_active=True, pk__in=granted_ids)


ANNUAL_LEAVE_CODE = "annual"
ANNUAL_LEAVE_NAME = "Annual Leave"


def find_annual_leave_type() -> LeaveType | None:
    """Read-only lookup of the canonical annual type. Never writes."""
    for code in (ANNUAL_LEAVE_CODE, f"{ANNUAL_LEAVE_CODE}-leave"):
        try:
            return LeaveType.objects.get(code=code)
        except LeaveType.DoesNotExist:
            continue
    try:
        return LeaveType.objects.get(name__iexact=ANNUAL_LEAVE_NAME)
    except LeaveType.DoesNotExist:
        return None


def get_or_create_annual_leave_type() -> tuple[LeaveType, bool]:
    """Adopt-or-create the canonical annual leave type."""
    annual = find_annual_leave_type()
    if annual is not None:
        return annual, False
    return (
        LeaveType.objects.create(
            name=ANNUAL_LEAVE_NAME,
            code=ANNUAL_LEAVE_CODE,
            is_active=True,
        ),
        True,
    )


def ensure_annual_leave_rule(
    leave_type: LeaveType, effective_from: date, max_duration_days: int
) -> LeaveRule | None:
    """Create the default effective rule, or None when one already exists."""
    if leave_type.rules.exists():
        return None
    return LeaveRule.objects.create(
        leave_type=leave_type,
        max_duration_days=max_duration_days,
        eligibility="",
        eligibility_rules=[],
        min_notice_days=0,
        requires_supporting_document=False,
        consumes_annual_entitlement=True,
        effective_from=effective_from,
    )


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


def financial_year_label(year: FinancialYear) -> str:
    """Derive the canonical short label for a financial year.

    LUANAR years span calendar years (e.g. ``2026-07-01`` → ``2027-06-30``);
    the label is the start year joined with the last two digits of the end
    year (``2026-27``). The label is a derivation, not a stored column.
    """
    return f"{year.start_date.year}-{str(year.end_date.year)[-2:]}"


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