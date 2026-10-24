"""The one path every module uses to read or change a leave type's rules.

Refinement unit 06: ``leave_config`` owns ``LeaveType``, so the value of a rule
(``notice_days``, ``max_duration_days``, ``requires_supporting_document``,
``plannable``, ``consumes_annual_entitlement``, the three eligibility
dimensions) is read here rather than copied onto another model or re-derived
inline.  Nothing else stores a leave-type rule (§6).

The date maths for the notice rule lives here too, so Unit 14's submission
validator and the Leave Plans reminder can never disagree about what "enough
notice" means (§1.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import record_audit
from leave_types.models import BranchScope, GenderEligibility, LeaveType
from users.models import User

__all__ = [
    "ANNUAL_LEAVE_CODE",
    "ANNUAL_LEAVE_CODES",
    "ANNUAL_LEAVE_NAME",
    "AnnualLeaveLifecycleError",
    "NoticeCheck",
    "can_access_leave_config",
    "check_notice",
    "consumes_annual_entitlement",
    "day_unit_for",
    "deactivate_leave_type",
    "ensure_annual_leave_policy",
    "find_annual_leave_type",
    "get_max_duration_days",
    "get_notice_days",
    "get_or_create_annual_leave_type",
    "get_requires_supporting_document",
    "is_annual_leave_identity",
    "is_annual_leave_type",
    "is_eligible",
    "is_plannable",
    "normalize_leave_code",
    "provision_annual_leave",
    "reactivate_leave_type",
    "validate_notice",
]


# -- Access -----------------------------------------------------------------


def can_access_leave_config(user) -> bool:
    return can_access_leave_types(user)


def can_access_leave_types(user) -> bool:
    """HR (or anyone administering the system) may configure leave types."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return getattr(user, "role", None) == User.Role.HR


def _resolve(leave_type: LeaveType | int) -> LeaveType:
    """Accept a ``LeaveType`` or its primary key."""
    if isinstance(leave_type, LeaveType):
        return leave_type
    return LeaveType.objects.get(pk=leave_type)


def get_notice_days(leave_type: LeaveType | int) -> int | None:
    """Advance notice (days) this type requires; ``None`` means no minimum."""
    return _resolve(leave_type).notice_days


def get_max_duration_days(leave_type: LeaveType | int) -> int | None:
    """Longest single application in days; ``None`` means no maximum."""
    return _resolve(leave_type).max_duration_days


def get_requires_supporting_document(leave_type: LeaveType | int) -> bool:
    return _resolve(leave_type).requires_supporting_document


def is_plannable(leave_type: LeaveType | int) -> bool:
    """Whether this type may appear on the Leave Plans "Create a Plan" form."""
    return _resolve(leave_type).plannable


def consumes_annual_entitlement(leave_type: LeaveType | int) -> bool:
    """Whether applying for this type draws down the annual leave balance."""
    return _resolve(leave_type).consumes_annual_entitlement


# -- Lifecycle (§1.5 — deactivate, never delete) ----------------------------


class AnnualLeaveLifecycleError(ValueError):
    """Raised when something tries to retire the annual leave type.

    Annual leave is the one type every employee must keep selecting: an
    entitlement provisions it and the balance ledger resolves to it, so retiring
    it would empty the leave selection everywhere. The rule lives in the service
    rather than in the view or the form alone because those are two of three
    callers — the Django admin's lifecycle actions are the third, and each of
    them would otherwise need its own copy of the check.

    Reactivating is deliberately *not* refused: if an annual type is somehow
    already retired, putting it back is a repair, not a second way to retire it.
    """


@transaction.atomic
def deactivate_leave_type(leave_type: LeaveType, actor) -> None:
    """Hide a type from new applications/plans, leaving history untouched."""
    if is_annual_leave_type(leave_type):
        raise AnnualLeaveLifecycleError(
            f"{leave_type.name} is provisioned by an entitlement and is offered "
            "to every employee, so it cannot be deactivated."
        )
    if not leave_type.is_active:
        return
    leave_type.is_active = False
    leave_type.save(update_fields=["is_active", "updated_at"])
    _record_lifecycle_audit(leave_type, actor, AuditEntry.Action.DEACTIVATED)


@transaction.atomic
def reactivate_leave_type(leave_type: LeaveType, actor) -> None:
    """Put a retired type back into the active dropdowns.

    The annual type is deliberately allowed through: restoring it is a repair,
    not a second way to retire it (:class:`AnnualLeaveLifecycleError`).
    """
    if leave_type.is_active:
        return
    leave_type.is_active = True
    leave_type.save(update_fields=["is_active", "updated_at"])
    _record_lifecycle_audit(leave_type, actor, AuditEntry.Action.ACTIVATED)


def _record_lifecycle_audit(leave_type: LeaveType, actor, action: str) -> None:
    record_audit(
        actor=actor,
        action=action,
        target_type=AuditEntry.TargetType.LEAVE_TYPE,
        target_id=leave_type.pk,
        target_summary=str(leave_type),
        detail={
            "before": {"is_active": not (action == AuditEntry.Action.ACTIVATED)},
            "after": {"is_active": action == AuditEntry.Action.ACTIVATED},
        },
    )


# -- Eligibility (§1.4 — three independently optional dimensions) -----------


def _employee_dimensions(employee) -> tuple[str | None, str | None, str | None]:
    """``(branch, grade, gender)`` for an employee; ``None`` when unknown.

    ``employee`` may be a :class:`~users.models.User` (branch comes from the
    organisation provider, grade/gender from the profile) or anything carrying
    those attributes already (the validation pipeline's ``EmployeeInfo``, the
    provider's ``EmployeeRecord``).
    """
    branch = getattr(employee, "branch", None)
    grade = getattr(employee, "grade", None) or getattr(employee, "grade_id", None)
    gender = getattr(employee, "gender", None)

    profile = getattr(employee, "employee_profile", None)
    if profile is not None:
        grade = grade or getattr(profile, "grade", None) or None
        gender = gender or getattr(profile, "gender", None) or None

    if branch is None:
        from directory.services import find_provider_employee_for_user

        record = find_provider_employee_for_user(employee)
        if record is not None:
            branch = record.branch
            grade = grade or record.grade_id
            gender = gender or record.gender

    return (
        branch,
        str(grade).strip() or None if grade else None,
        str(gender).strip() or None if gender else None,
    )


def is_eligible(leave_type: LeaveType | int, employee) -> bool:
    """Whether *employee* may apply for *leave_type*.

    Each of the three dimensions is checked independently; a dimension that is
    unrestricted on the type (``BOTH``, empty grade list, ``ANY``) always
    passes.  A dimension that *is* restricted but cannot be resolved for this
    employee fails closed, matching the validation pipeline's rule that missing
    eligibility data blocks rather than allows.
    """
    leave_type = _resolve(leave_type)
    branch, grade, gender = _employee_dimensions(employee)

    if leave_type.branch_scope != BranchScope.BOTH:
        if branch is None or str(branch).strip().lower() != leave_type.branch_scope:
            return False

    allowed_grades = leave_type.eligible_grade_ids
    if allowed_grades:
        if grade is None or grade.upper() not in allowed_grades:
            return False

    if leave_type.eligible_gender != GenderEligibility.ANY:
        if gender is None or gender.lower() != leave_type.eligible_gender:
            return False

    return True


# -- Notice (§1.2 — one field, two consumers) -------------------------------


@dataclass(frozen=True)
class NoticeCheck:
    """A notice requirement that has **not** been met."""

    required: int
    given: int
    unit: str
    earliest_start: date

    @property
    def unit_label(self) -> str:
        return "working days" if self.unit == "working_days" else "calendar days"


def day_unit_for(leave_type: LeaveType | int) -> str:
    """The unit this type's day-based rules are counted in.

    Annual leave is counted in working days; everything else in calendar days.
    (Moved here from ``leave.providers.database`` so duration and notice can
    never be counted in different units for the same type.)
    """
    # Resolved at call time: ``ANNUAL_LEAVE_CODES`` is declared below.
    code = (_resolve(leave_type).code or "").strip().lower()
    return "working_days" if code in ANNUAL_LEAVE_CODES else "calendar_days"


def _earliest_start(today: date, notice: int, unit: str, holidays: set) -> date:
    """The earliest start date that satisfies the notice requirement."""
    if unit == "calendar_days":
        earliest = today + timedelta(days=notice)
        return earliest if earliest > today else today + timedelta(days=1)

    from leave.validation.working_days import count_working_days

    candidate = date.fromordinal(today.toordinal() + 1)
    while count_working_days(
        date.fromordinal(today.toordinal() + 1), candidate, holidays
    ) < notice:
        candidate = date.fromordinal(candidate.toordinal() + 1)
    return candidate


def check_notice(
    leave_type: LeaveType | int,
    start_date: date,
    *,
    today: date | None = None,
    holidays=(),
) -> NoticeCheck | None:
    """Return why *start_date* is too soon, or ``None`` when it is far enough.

    ``None`` is also returned when the type sets no notice requirement.  The
    caller is expected to have established that ``start_date`` and ``today``
    exist; this function is the calculation only, so Unit 14's validator can
    turn the result into a field-level issue with its own message and detail.
    """
    leave_type = _resolve(leave_type)
    notice = leave_type.notice_days
    if not notice:
        return None

    today = today or timezone.localdate()
    unit = day_unit_for(leave_type)
    holiday_set = set(holidays)

    if unit == "calendar_days":
        given = (start_date - today).days
    else:
        from leave.validation.working_days import working_days_elapsed

        given = working_days_elapsed(today, start_date, holiday_set)

    if given >= notice:
        return None
    return NoticeCheck(
        required=notice,
        given=given,
        unit=unit,
        earliest_start=_earliest_start(today, notice, unit, holiday_set),
    )


def validate_notice(
    leave_type: LeaveType | int,
    start_date: date,
    *,
    today: date | None = None,
    holidays=(),
) -> bool:
    """Whether *start_date* honours the type's notice requirement.

    ``notice_days is None`` (or 0) means no minimum, which is always valid.
    This is the §4.3 helper; Unit 14's validator calls :func:`check_notice`
    instead so it can report the earliest permissible start date.
    """
    leave_type = _resolve(leave_type)
    if not leave_type.notice_days:
        return True
    return (
        check_notice(
            leave_type, start_date, today=today, holidays=holidays
        )
        is None
    )


# -- The reserved annual leave identity -------------------------------------
#
# Annual leave is not a registry entry HR curates: it is provisioned by saving
# an entitlement, and it must never be created, renamed or retired by hand from
# the Leave Configuration screens either. The constants and the write guard live
# here rather than in ``leave`` because they are a rule about this registry.


ANNUAL_LEAVE_CODE = "annual"
#: Every code :func:`find_annual_leave_type` treats as the canonical annual
#: type. Held as a constant because the write guard
#: (:func:`is_annual_leave_identity`) and the read lookup must recognise the
#: same rows; a second hand-written copy of this list is how a second
#: "Annual Leave" gets created.
ANNUAL_LEAVE_CODES = frozenset({ANNUAL_LEAVE_CODE, f"{ANNUAL_LEAVE_CODE}-leave"})
ANNUAL_LEAVE_NAME = "Annual Leave"


def normalize_leave_code(value: str) -> str | None:
    """Slugify a leave-type code; ``None`` when blank."""
    from django.utils.text import slugify

    text = (value or "").strip()
    if not text:
        return None
    return slugify(text)


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
    which is the value :meth:`LeaveType.save` would store.

    Both halves of the lookup are checked because :meth:`LeaveType.save`
    slugifies the name into the code: "Annual Leave" arrives as code
    ``annual-leave``, so a name-only check would wave it through.
    """
    normalized_code = normalize_leave_code(code if isinstance(code, str) else "")
    if normalized_code is not None and normalized_code in ANNUAL_LEAVE_CODES:
        return True
    normalized_name = name.strip() if isinstance(name, str) else ""
    return bool(normalized_name) and normalized_name.casefold() == (
        ANNUAL_LEAVE_NAME.casefold()
    )


def get_or_create_annual_leave_type(*, days: int | None = None) -> tuple[
    LeaveType, bool
]:
    """Adopt-or-create the canonical annual leave type.

    ``days`` is the entitlement being written: a row created here comes into
    being already carrying the duration it needs, so provisioning audits one
    ``created`` entry instead of a create followed by an immediate fix-up.
    """
    annual = find_annual_leave_type()
    if annual is not None:
        return annual, False
    defaults = {
        "is_active": True,
        "consumes_annual_entitlement": True,
    }
    if days is not None:
        defaults["max_duration_days"] = days
    return (
        LeaveType.objects.create(
            name=ANNUAL_LEAVE_NAME,
            code=ANNUAL_LEAVE_CODE,
            **defaults,
        ),
        True,
    )


def ensure_annual_leave_policy(leave_type: LeaveType, days: int) -> bool:
    """Give the annual type its baseline policy if it has none yet.

    Returns whether anything was written. The only fields worth defaulting are
    the two the entitlement itself implies — annual leave consumes the annual
    balance, and it needs *some* duration for the employee catalog to display —
    and both are only set when HR has not already configured them, so this can
    never overwrite a policy an administrator edited.
    """
    if leave_type.consumes_annual_entitlement and leave_type.max_duration_days:
        return False
    if not leave_type.consumes_annual_entitlement:
        leave_type.consumes_annual_entitlement = True
    if not leave_type.max_duration_days:
        leave_type.max_duration_days = days
    leave_type.save(
        update_fields=["consumes_annual_entitlement", "max_duration_days", "updated_at"]
    )
    return True


def provision_annual_leave(*, days: int, actor=None) -> LeaveType:
    """Adopt-or-create annual leave and guarantee it has its policy.

    The single authoritative implementation of annual-leave provisioning. An
    entitlement *is* an annual-leave entitlement, so this is what runs when HR
    saves one: the leave type comes into being here and nowhere else, which is
    why the Leave Configuration form refuses to create or rename it (see
    :func:`is_annual_leave_identity`).

    Idempotent, so the second band of a grade range costs one existence check.
    Each row written here is audited, because an entitlement's real effect on
    configuration is larger than the band row the admin table shows.
    """
    annual, created = get_or_create_annual_leave_type(days=days)
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
                    "max_duration_days": annual.max_duration_days,
                    "consumes_annual_entitlement": annual.consumes_annual_entitlement,
                },
            },
        )

    # A row created above already carries the policy, so this second audit
    # only ever fires when HR's existing configuration had to be completed.
    if ensure_annual_leave_policy(annual, days):
        annual.refresh_from_db()
        record_audit(
            actor=actor,
            target_type=AuditEntry.TargetType.LEAVE_TYPE,
            target_id=annual.pk,
            action=AuditEntry.Action.UPDATED,
            target_summary=str(annual),
            detail={
                "summary": f"Applied the default annual leave policy for {annual.name}",
                "before": None,
                "after": {
                    "max_duration_days": annual.max_duration_days,
                    "consumes_annual_entitlement": (
                        annual.consumes_annual_entitlement
                    ),
                },
            },
        )
    return annual
