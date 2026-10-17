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
    """Return active leave types for selection.

    The application form should list all configured active leave types so HR
    can manage types centrally; entitlement/eligibility determine whether a
    particular employee may actually take a given type at submission time.
    """
    return LeaveType.objects.filter(is_active=True)


ANNUAL_LEAVE_CODE = "annual"
#: Every code :func:`find_annual_leave_type` treats as the canonical annual
#: type. Held as a constant because the write guard (:func:`is_annual_leave_identity`)
#: and the read lookup must recognise the same rows; a second hand-written copy
#: of this list is how a second "Annual Leave" gets created.
ANNUAL_LEAVE_CODES = frozenset({ANNUAL_LEAVE_CODE, f"{ANNUAL_LEAVE_CODE}-leave"})
ANNUAL_LEAVE_NAME = "Annual Leave"


def find_annual_leave_type() -> LeaveType | None:
    """Read-only lookup of the canonical annual type. Never writes."""
    for code in sorted(ANNUAL_LEAVE_CODES):
        try:
            return LeaveType.objects.get(code=code)
        except LeaveType.DoesNotExist:
            continue
    try:
        return LeaveType.objects.get(name__iexact=ANNUAL_LEAVE_NAME)
    except LeaveType.DoesNotExist:
        return None


def is_annual_leave_type(leave_type: LeaveType | None) -> bool:
    """Whether ``leave_type`` is the canonical annual type.

    Resolved through :func:`find_annual_leave_type` rather than comparing codes
    at each call site, so a database that already holds an annual type under
    either recognised code is honoured instead of being told it has none.
    """
    if leave_type is None:
        return False
    annual = find_annual_leave_type()
    return annual is not None and annual.pk == leave_type.pk


def is_annual_leave_identity(name: object, code: object) -> bool:
    """Whether a name/code pair would claim the canonical annual type.

    The write-side twin of :func:`is_annual_leave_type`, and the reason it
    exists: a leave type becomes canonical the moment it is saved, so the guard
    has to answer the question *before* there is a row to compare against.
    ``code`` is the effective code (already slugified, or derived from the name),
    which is the value ``LeaveType.save`` would store.

    Both halves of the lookup are checked because ``LeaveType.save`` slugifies
    the name into the code: "Annual Leave" arrives as code ``annual-leave``, so a
    name-only check would wave it through.
    """
    normalized_code = normalize_leave_code(code if isinstance(code, str) else "")
    if normalized_code is not None and normalized_code in ANNUAL_LEAVE_CODES:
        return True
    normalized_name = name.strip() if isinstance(name, str) else ""
    return bool(normalized_name) and normalized_name.casefold() == (
        ANNUAL_LEAVE_NAME.casefold()
    )


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


def provision_annual_leave(
    *, effective_from: date, days: int, actor=None
) -> LeaveType:
    """Adopt-or-create annual leave and guarantee it has a rule. Returns the type.

    The single authoritative implementation of annual-leave provisioning. An
    entitlement *is* an annual-leave entitlement, so this is what runs when HR
    saves one: the leave type and its first :class:`LeaveRule` come into being
    here and nowhere else, which is why the leave-type form cannot create or
    rename them (see :class:`~leave.serializers.LeaveTypeSerializer`).

    The rule is what makes annual leave visible in HR's Leave Rules table and
    what gives the employee catalog a duration to show, so provisioning the type
    without it would leave a granted entitlement invisible in both places. Only
    the first rule is created: later bands adjust the entitlement's ``days``,
    and the type's policy is effective-dated configuration HR edits under Leave
    Rules.

    Idempotent, so the second band of a grade range costs one existence check.
    Each row written here is audited, because an entitlement's real effect on
    configuration is larger than the band row the admin table shows.
    """
    from audit.models import AuditEntry
    from audit.services import record_audit

    annual, created = get_or_create_annual_leave_type()
    if created:
        record_audit(
            actor=actor,
            target_type=AuditEntry.TargetType.LEAVE_TYPE,
            target_id=annual.pk,
            action=AuditEntry.Action.CREATED,
            target_summary=str(annual),
            detail={
                "summary": (
                    f"Created leave type {annual.name} ({annual.code}) for the "
                    "annual leave entitlement"
                ),
                "before": None,
                "after": {
                    "name": annual.name,
                    "code": annual.code,
                    "is_active": annual.is_active,
                },
            },
        )

    rule = ensure_annual_leave_rule(annual, effective_from, days)
    if rule is not None:
        record_audit(
            actor=actor,
            target_type=AuditEntry.TargetType.LEAVE_RULE,
            target_id=rule.pk,
            action=AuditEntry.Action.CREATED,
            target_summary=str(rule),
            detail={
                "summary": f"Created the default leave rule for {annual.name}",
                "before": None,
                "after": {
                    "leave_type": annual.pk,
                    "max_duration_days": rule.max_duration_days,
                    "eligibility": rule.eligibility,
                    "eligibility_rules": rule.eligibility_rules,
                    "min_notice_days": rule.min_notice_days,
                    "requires_supporting_document": (
                        rule.requires_supporting_document
                    ),
                    "consumes_annual_entitlement": (
                        rule.consumes_annual_entitlement
                    ),
                    "effective_from": rule.effective_from.isoformat(),
                },
            },
        )
    return annual


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


# Imported last so ``dashboard`` can read the names above from this package
# without a circular-import failure.
from .dashboard import get_dashboard_data  # noqa: E402,F401
from .drafts import create_draft_application  # noqa: E402,F401
