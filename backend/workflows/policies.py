<<<<<<< HEAD
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
=======
"""Approver decision and visibility rules (Unit 16, spec 5).

These are the single source of truth for *who may decide* and *who may view*
an application. The API consults them; the decision service enforces them
under row locks; tests pin every case in spec table 5-D.

:func:`is_self_application` is the one authoritative applicant-identity check.
It is shared by the decision guard, the HR reassignment validation (Unit 9) and
the cancellation guard (Unit 18) so the rule exists in a single place, and it is
the predicate the workflow-stage skip logic keys off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from leave.models import LeaveApplication
from users.models import EmployeeProfile, User

from .models import ApplicationStage, ApprovalDecision, ApproverRole
>>>>>>> feature/plans-teams


@dataclass(frozen=True)
class Authority:
<<<<<<< HEAD
    """Whether ``user`` may decide on ``application`` right now."""
=======
    """Whether ``user`` may decide on the application, with a reason code.

    ``reason`` is one of ``self_application``, ``application_closed``,
    ``already_decided`` or ``not_current_stage`` when ``can_decide`` is false.
    """
>>>>>>> feature/plans-teams

    can_decide: bool
    reason: str | None = None


<<<<<<< HEAD
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


def can_view_approved_document(user, application) -> bool:
    """Return whether ``user`` may stream the official approved-leave PDF.

    True for the employee, every workflow member (approvers in the
    application's snapshot), HR, and any approver who reached the application
    (the Unit 16 ``get_view_access`` fallback). Callers respond 404 when this
    is false, never 403, so existence is not leaked.
    """
    if application.employee_id == user.id:
        return True
    from users.models import User

    if getattr(user, "role", None) == User.Role.HR:
        return True
    from .providers import get_workflow_provider

    member_ids = get_workflow_provider().get_workflow_member_user_ids(application)
    if user.id in member_ids:
        return True
    return get_view_access(user, application) is not None


def _already_decided(user, application) -> bool:
    return ApprovalDecision.objects.filter(
        application=application,
        approver=user,
=======
def is_self_application(user, application: LeaveApplication) -> bool:
    """Whether ``user`` is the applicant who owns ``application``.

    The single authoritative applicant check. ``LeaveApplication.employee`` is a
    direct FK to the user model, so the comparison is on ``employee_id``.

    ``user`` may be a loaded ``User`` or a bare user id: stage assignment
    compares resolved ``StageDefinition.approver_user_id`` values before any
    user row is loaded, so both call styles are supported.

    Used to keep an approver from ever being the approver of record for their
    own leave: HR reassignment refuses it (Unit 9), a cancellation decision
    refuses it (Unit 18), :func:`get_decision_authority` refuses it, and stage
    assignment skips the stage that would resolve to the applicant.
    """
    if user is None or application is None:
        return False
    user_id = user if isinstance(user, int) else user.pk
    return application.employee_id == user_id


def get_decision_authority(user: User, application: LeaveApplication) -> Authority:
    """Grant or deny the ability to decide on ``application``.

    Every approval request is checked against the application's *current*
    live state, so a completed application rejects further decisions. An
    approver may never decide on their own application, no matter where the
    chain is. This check is independent of stage assignment: it holds even in
    a state where assignment logic was bypassed.
    """
    if is_self_application(user, application):
        return Authority(False, "self_application")

    if application.status != LeaveApplication.Status.SUBMITTED:
        return Authority(False, "application_closed")

    from .services import user_may_act

    stage = _current_stage(application)
    if stage is None:
        return Authority(False, "application_closed")
    if stage.status != ApplicationStage.Status.PENDING:
        return Authority(False, "already_decided")
    if _decided_this_cycle(user, application):
        return Authority(False, "already_decided")
    if not user_may_act(user, application):
        return Authority(False, "not_current_stage")
    return Authority(True, None)


@dataclass(frozen=True)
class ViewAccess:
    """A viewable application resolved for one approver.

    ``history_scope`` is the approver role's configured leave-history scope,
    resolved from the stage's ``role_ref`` (falling back to a lookup by the
    snapshotted code for rows written before roles became data). Carrying it
    here keeps the role out of every caller's hands: display always uses
    ``role_label``, the snapshot, and never the live role.
    """

    stage_order: int
    role: str
    role_label: str
    stage: ApplicationStage | None = None
    history_scope: str | None = None


def _role_for_stage(stage: ApplicationStage):
    """The live :class:`ApproverRole` a stage was materialised from, or ``None``.

    Prefers the snapshotted FK. Rows written before roles became data have a
    null ``role_ref``, so the snapshotted ``role`` code is looked up instead —
    still reading the *stage*, never a live stage of a running application.
    """
    from .models import ApproverRole

    if stage.role_ref_id is not None:
        return stage.role_ref
    if not stage.role:
        return None
    return ApproverRole.objects.filter(code=stage.role).first()


def _history_scope_for(stage: ApplicationStage | None) -> str | None:
    """The history scope an in-flight stage is judged by: its own snapshot.

    Read from ``ApplicationStage.history_scope`` rather than from the live role,
    so an in-flight application keeps the breadth it was submitted under even if
    HR later widens or narrows the role. Falls back to the live role only for
    rows written before the snapshot existed (blank ``history_scope``), and to
    the narrowest scope when neither is available — a missing scope can never
    widen an approver's view.
    """
    if stage is None:
        return None
    if stage.history_scope:
        return stage.history_scope
    role = _role_for_stage(stage)
    if role is None:
        return ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR
    return role.history_scope


def get_view_access(user: User, application: LeaveApplication) -> ViewAccess | None:
    """The application's stage the user can review, or ``None`` (404).

    The user must be the assigned approver of at least one stage of the live
    submission cycle that has been reached — i.e. the application must have got
    to them, or they must already have decided on it. A ``waiting`` stage has
    not been reached, so it confers no access.

    Unit 18: an approver assigned to a cancellation stage may also read the
    approved application's review payload, even though the application is no
    longer ``submitted``. The ``stage`` of such a ``ViewAccess`` is ``None``.
    """
    from leave.cancellations.models import CancellationApprovalStage
    from .services import user_may_act

    live_stage = (
        application.stages.filter(
            submission_cycle=application.workflow_chain_cycle,
            status=ApplicationStage.Status.PENDING,
        )
        .first()
    )
    if live_stage is not None and user_may_act(user, application):
        return ViewAccess(
            live_stage.stage_order,
            live_stage.role,
            live_stage.role_label,
            live_stage,
            _history_scope_for(live_stage),
        )

    stage = (
        application.stages.filter(
            assigned_approver=user,
            submission_cycle=application.workflow_chain_cycle,
        )
        .exclude(status=ApplicationStage.Status.WAITING)
        .first()
    )
    if stage is not None:
        return ViewAccess(
            stage.stage_order,
            stage.role,
            stage.role_label,
            stage,
            _history_scope_for(stage),
        )

    cancellation_stage = (
        CancellationApprovalStage.objects.filter(
            request__application=application,
            eligible_approvers__user=user,
        )
        .exclude(status=CancellationApprovalStage.Status.NOT_REACHED)
        .distinct()
        .order_by("order")
        .first()
    )
    if cancellation_stage is not None:
        # A cancellation stage carries only the snapshotted role code and label,
        # so the scope has to be looked up by that code. A role HR has since
        # renamed still resolves, because the code is the snapshot's own value.
        from .models import ApproverRole

        role = ApproverRole.objects.filter(code=cancellation_stage.role).first()
        return ViewAccess(
            cancellation_stage.order,
            cancellation_stage.role,
            cancellation_stage.role_label,
            None,
            role.history_scope if role is not None else None,
        )
    return None


def get_leave_history_scope(
    view_access: ViewAccess,
    employee_profile: EmployeeProfile | None,
    approver_profile: EmployeeProfile | None,
) -> tuple[bool, str]:
    """Resolve the leave-history subset visible to an approver.

    Returns ``(available, scope)``, where ``scope`` is the subset the caller
    should read. Availability and breadth are HR's per-role decision, read from
    the role the stage was materialised with — not from a role name:

    ``all``                    every application.
    ``same_team``              only employees on the applicant's team, and only
                               when the approver is on it.
    ``same_campus``            only employees at the applicant's campus, and only
                               when the approver is at that campus.
    ``same_faculty``           likewise, on faculty.
    ``current_financial_year`` only the current financial year.
    ``none``                   nothing.

    A stage whose role cannot be resolved at all (a role deleted outside the
    product, say) falls back to the narrowest sensible reading — the current
    financial year — so a missing role can never widen an approver's view.
    """
    if view_access is None:
        return (False, "current_financial_year")
    scope = view_access.history_scope or ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR
    if scope == ApproverRole.HistoryScope.NONE:
        return (False, "none")
    if scope == ApproverRole.HistoryScope.ALL:
        return (True, "all")
    if scope == ApproverRole.HistoryScope.SAME_TEAM:
        same = _same_team(employee_profile, approver_profile)
        return (same, "all")
    if scope == ApproverRole.HistoryScope.SAME_CAMPUS:
        same = _same_campus(employee_profile, approver_profile)
        return (same, "all")
    if scope == ApproverRole.HistoryScope.SAME_FACULTY:
        same = _same_profile_field(employee_profile, approver_profile, "faculty")
        return (same, "all")
    return (True, "current_financial_year")



def _same_team(employee, approver) -> bool:
    """Whether both profiles sit on the same team.

    Compared by id, not by name: a team rename moves every reference with it, and
    an id comparison cannot be defeated by two teams that read identically.
    """
    if employee is None or approver is None:
        return False
    employee_team_id = getattr(employee, "team_id", None)
    return employee_team_id is not None and employee_team_id == approver.team_id


def _same_campus(employee, approver) -> bool:
    """Whether both profiles are at the same campus, read through their team.

    A campus is a property of the *team*, not of the employee: an employee is on
    a campus because their team is. An employee on no team is on no campus, and two
    unteamed employees are not "at the same campus" — an absent campus is not a
    shared one.
    """
    if employee is None or approver is None:
        return False
    employee_campus_id = getattr(getattr(employee, "team", None), "campus_id", None)
    approver_campus_id = getattr(getattr(approver, "team", None), "campus_id", None)
    return (
        employee_campus_id is not None
        and employee_campus_id == approver_campus_id
    )


def _same_profile_field(employee, approver, field: str) -> bool:
    if employee is None or approver is None:
        return False
    employee_value = _profile_value(employee, field)
    approver_value = _profile_value(approver, field)
    return employee_value and employee_value == approver_value


def _profile_value(profile, field: str) -> str:
    value = getattr(profile, field, "")
    return (value or "").strip().lower()


def _decided_this_cycle(user, application) -> bool:
    return ApprovalDecision.objects.filter(
        application_id=application.pk,
        approver_id=user.id,
>>>>>>> feature/plans-teams
        submission_cycle=application.submission_cycle,
    ).exists()


<<<<<<< HEAD
def _current_financial_year(application):
    """Return the (start, end) of the application's financial year, or None."""
    snapshot = application.rules_snapshot or {}
    fiscal = snapshot.get("financial_year")
    if fiscal and fiscal.get("start") and fiscal.get("end"):
        from datetime import date

        return (date.fromisoformat(fiscal["start"]), date.fromisoformat(fiscal["end"]))
    return None
=======
def _current_stage(application: LeaveApplication) -> ApplicationStage | None:
    if application.current_stage_id is None:
        return None
    return ApplicationStage.objects.filter(pk=application.current_stage_id).first()
>>>>>>> feature/plans-teams
