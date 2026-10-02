"""Department services: creation, retirement, and the employee reference.

Deliberately free of any import from :mod:`workflows`. ``Department`` is
employee data — it says who somebody belongs to — and ``Team`` merely holds one,
so the dependency between the two apps points ``workflows`` → ``users``, which is
the direction Django already applies. A service here that needed to ask about a
team would invert that and make the app cycle.
"""

from django.db import transaction
from django.db.models import Q

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit

from .models import Department


class DepartmentActionError(ValueError):
    """Raised when a department cannot be created or renamed as asked."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)


def normalize_department_name(name: object) -> str:
    """A department's name, trimmed, or a refusal.

    Trimming is not cosmetic. Two rows differing only by surrounding whitespace
    would be two departments that read identically in every picker, and the
    rule "an approver must be in the team's department" would then compare two
    strings HR could not tell apart.
    """
    cleaned = (name or "").strip() if isinstance(name, str) else ""
    if not cleaned:
        raise DepartmentActionError("name", "Enter a department name.")
    return cleaned


def resolve_department(name: str) -> Department | None:
    """The active department with this exact name, case-insensitively."""
    return (
        Department.objects.filter(name__iexact=name).order_by("pk").first()
    )


def create_department(*, actor, name: object) -> Department:
    """Create one department and audit it.

    Duplicate names are refused rather than folded into the existing row.
    Creating a department is how HR says "this is a real unit with its own
    teams"; silently reusing a row of the same name would answer a different
    question, and a near-miss ("ICT" against "Ict") is more likely to be a typo
    to correct than a synonym to merge.
    """
    cleaned = normalize_department_name(name)
    existing = resolve_department(cleaned)
    if existing is not None:
        raise DepartmentActionError(
            "name", f'A department named "{existing.name}" already exists.'
        )
    with transaction.atomic():
        department = Department.objects.create(name=cleaned)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.DEPARTMENT,
            target_id=department.pk,
            target_summary=department.name,
            detail={"before": None, "after": _department_snapshot(department)},
        )
    return department


def update_department(*, department: Department, actor, name: object) -> Department:
    """Rename a department and audit the change.

    The name is only ever a label on the row; teams and employees reference it by
    id, so a rename moves every reference with it and cannot orphan an
    approver's eligibility.
    """
    cleaned = normalize_department_name(name)
    if cleaned == department.name:
        return department
    clash = Department.objects.filter(name__iexact=cleaned).exclude(pk=department.pk)
    if clash.exists():
        raise DepartmentActionError(
            "name", f'A department named "{cleaned}" already exists.'
        )
    with transaction.atomic():
        department = Department.objects.select_for_update().get(pk=department.pk)
        before = _department_snapshot(department)
        department.name = cleaned
        department.save(update_fields=["name", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.DEPARTMENT,
            target_id=department.pk,
            target_summary=department.name,
            detail=changed_fields(before, _department_snapshot(department)),
        )
    return department


def retire_department(*, department: Department, actor) -> Department:
    """Retire a department, refusing while a team or employee still needs it.

    Retirement rather than deletion: teams and employee records reference the
    row, and a historical ``ApplicationStage`` names the department as text. A
    department that is still on a team is not history, it is in use.
    """
    if not department.is_active:
        return department
    in_use = (
        department.teams.exists() or department.employees.exists()
    )
    if in_use:
        raise DepartmentActionError(
            "name",
            f'"{department.name}" is still on a team or an employee record. Move '
            "them to another department before retiring it.",
        )
    with transaction.atomic():
        department = Department.objects.select_for_update().get(pk=department.pk)
        if not department.is_active:
            return department
        before = _department_snapshot(department)
        department.is_active = False
        department.save(update_fields=["is_active", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.DEPARTMENT,
            target_id=department.pk,
            target_summary=department.name,
            detail=changed_fields(before, _department_snapshot(department)),
            reason="Department retired by HR.",
        )
    return department


def department_employees(department: Department | None):
    """Active employee profiles in ``department``, by user name.

    Eligibility for an approver post is an employment question, so it is
    answered here rather than in each caller: an employee in the team's
    department is somebody with an active profile in that department.
    """
    from .models import EmployeeProfile

    if department is None:
        return EmployeeProfile.objects.none()
    return (
        EmployeeProfile.objects.filter(department=department, user__is_active=True)
        .select_related("user", "team")
        .order_by("user__first_name", "user__last_name")
    )


def department_member_count(department: Department) -> int:
    """Active employees recorded in this department."""
    from .models import EmployeeProfile

    return EmployeeProfile.objects.filter(
        department=department, user__is_active=True
    ).count()


def employee_department(employee_profile) -> Department | None:
    """The department an employee record sits in, if any."""
    return getattr(employee_profile, "department", None)


def employee_in_department(employee_profile, department: Department | None) -> bool:
    """Whether this employee may be appointed on a team in ``department``.

    A team with no department cannot scope an approver, so nothing is eligible:
    claiming "anybody may approve for an unscoped team" would make the
    department restriction unenforceable the moment HR left the field blank.
    """
    if department is None or employee_profile is None:
        return False
    return employee_profile.department_id == department.pk


def department_search_term(term: str) -> Q:
    """Filter matching a department name loosely, for HR's search box."""
    return Q(name__icontains=term)


def _department_snapshot(department: Department) -> dict:
    return {"name": department.name, "is_active": department.is_active}