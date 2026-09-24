"""Unit 16 authority and visibility policies.

This module is the **only** place the "may the user act / may the user see"
decisions for approvals are made. Later units (delegation, reassignment) extend
these functions only.
"""

from dataclasses import dataclass

from leave.models import LeaveApplication, SupportingDocument

from .models import ApplicationStage, ApprovalDecision
from .utils import leave_type_name

# Roles an employee-information matrix can be tightened per-role in later.
# Today every approver role sees the same whitelist (the matrix is uniform),
# so the serializer whitelists the fields and this map is where a future
# role-specific split would live.
EMPLOYEE_INFO_FIELDS = {
    "supervisor": ("full_name", "staff_id", "designation", "department", "faculty", "grade", "date_of_appointment"),
    "hod": ("full_name", "staff_id", "designation", "department", "faculty", "grade", "date_of_appointment"),
    "dean": ("full_name", "staff_id", "designation", "department", "faculty", "grade", "date_of_appointment"),
    "registrar": ("full_name", "staff_id", "designation", "department", "faculty", "grade", "date_of_appointment"),
    "dvc": ("full_name", "staff_id", "designation", "department", "faculty", "grade", "date_of_appointment"),
}

DECISIONABLE_STATUSES = (
    LeaveApplication.Status.SUBMITTED,
    LeaveApplication.Status.PENDING,
)


@dataclass(frozen=True)
class Authority:
    """Whether ``user`` may decide on ``application`` right now."""

    can_decide: bool
    reason: str | None = None


@dataclass(frozen=True)
class ViewAccess:
    """View permission for one application, carrying the viewer's stage."""

    stage: ApplicationStage
    role: str


def get_decision_authority(user, application) -> Authority:
    """Return whether ``user`` can decide on ``application``.

    ``can_decide`` is true only when all hold:
    1. the application status is submitted/pending;
    2. ``current_stage`` is ``pending``;
    3. the current stage's assigned approver is ``user``.
    Otherwise ``reason`` is one of ``application_cancelled``,
    ``application_closed``, ``not_current_stage`` or ``already_decided``.
    ``application_cancelled`` is distinct so the API returns 409 (section 3.8)
    while other closures stay 403.
    """
    if (
        application.status == LeaveApplication.Status.CANCELLED
        and application.cancelled_at is not None
    ):
        return Authority(False, "application_cancelled")
    if application.status not in DECISIONABLE_STATUSES:
        return Authority(False, "application_closed")

    stage = application.current_stage
    if (
        stage is None
        or stage.status != ApplicationStage.Status.PENDING
        or stage.assigned_approver_id != user.id
    ):
        if _already_decided(user, application):
            return Authority(False, "already_decided")
        return Authority(False, "not_current_stage")

    return Authority(True, None)


def get_view_access(user, application) -> ViewAccess | None:
    """Grant ``user`` view access to ``application`` or return ``None``.

    A user may view only if they are the assigned approver of at least one
    stage that is **not** still ``waiting`` (the application has reached them).
    ``None`` makes the API respond 404 so existence is never leaked. The
    returned object carries the user's stage (and its role) for this
    application; the viewer role used for the matrices elsewhere is the stage
    role, not the user's global role.
    """
    reached = [
        stage
        for stage in application.stages.all()
        if stage.assigned_approver_id == user.id
        and stage.status != ApplicationStage.Status.WAITING
    ]
    if not reached:
        return None
    earliest = min(reached, key=lambda stage: stage.stage_order)
    return ViewAccess(stage=earliest, role=earliest.role)


@dataclass(frozen=True)
class HistoryScope:
    """Whether and how much leave history the viewer may see."""

    available: bool
    scope: str | None  # "all", "current_financial_year", or None


def get_leave_history_scope(
    view_access: ViewAccess | None, employee
) -> HistoryScope:
    """Decide the employee's leave-history scope for the viewer's stage role.

    Supervisor: full history. HOD: full history only when the employee's
    department equals the HOD's department. Dean: full history only when the
    employee's faculty equals the Dean's faculty. Registrar/DVC: current
    financial year only. Missing view access, approver employee record,
    department or faculty fails closed (empty history).
    """
    if view_access is None:
        return HistoryScope(False, None)

    role = view_access.role
    if role == "supervisor":
        return HistoryScope(True, "all")

    if role in ("hod", "dean"):
        approver = view_access.stage.assigned_approver
        approver_profile = getattr(approver, "employee_profile", None)
        employee_profile = getattr(employee, "employee_profile", None)
        approver_unit = (
            approver_profile.department.strip() if approver_profile else ""
        )
        employee_unit = employee_profile.department.strip() if employee_profile else ""
        if not approver_unit or not employee_unit:
            return HistoryScope(False, None)
        if approver_unit.lower() == employee_unit.lower():
            return HistoryScope(True, "all")
        return HistoryScope(False, None)

    if role in ("registrar", "dvc"):
        return HistoryScope(True, "current_financial_year")

    return HistoryScope(False, None)


def get_leave_history(view_access: ViewAccess, application) -> dict:
    """Assemble the leave-history block for the review payload.

    Returns ``{"available": bool, "scope": str|None, "items": [...]}`` where
    items are the employee's ``approved``/``cancelled`` leave, excluding the
    application under review, newest first.
    """
    scope = get_leave_history_scope(view_access, application.employee)
    if not scope.available:
        return {"available": False, "scope": None, "items": []}

    queryset = LeaveApplication.objects.filter(
        employee=application.employee,
        status__in=["approved", "cancelled"],
    ).exclude(id=application.id)

    if scope.scope == "current_financial_year":
        fiscal = _current_financial_year(application)
        if fiscal is None:
            return {"available": False, "scope": None, "items": []}
        start, end = fiscal
        queryset = queryset.filter(start_date__range=(start, end))

    items = [
        {
            "leave_type": leave_type_name(item),
            "start_date": item.start_date.isoformat() if item.start_date else None,
            "end_date": item.end_date.isoformat() if item.end_date else None,
            "working_days": item.working_days,
            "status": item.status,
        }
        for item in queryset.order_by("-start_date")
    ]
    return {"available": True, "scope": scope.scope, "items": items}


def document_belongs_to_application(
    application, document: SupportingDocument
) -> bool:
    """True when the document belongs to the application under review."""
    return document.application_id == application.id


def _already_decided(user, application) -> bool:
    return ApprovalDecision.objects.filter(
        application=application,
        approver=user,
        submission_cycle=application.submission_cycle,
    ).exists()


def _current_financial_year(application):
    """Return the (start, end) of the application's financial year, or None."""
    snapshot = application.rules_snapshot or {}
    fiscal = snapshot.get("financial_year")
    if fiscal and fiscal.get("start") and fiscal.get("end"):
        from datetime import date

        return (date.fromisoformat(fiscal["start"]), date.fromisoformat(fiscal["end"]))
    return None