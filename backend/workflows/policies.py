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

from .models import ApplicationStage, ApprovalDecision


@dataclass(frozen=True)
class Authority:
    """Whether ``user`` may decide on the application, with a reason code.

    ``reason`` is one of ``self_application``, ``application_closed``,
    ``already_decided`` or ``not_current_stage`` when ``can_decide`` is false.
    """

    can_decide: bool
    reason: str | None = None


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

    from .services import acting_approver_id

    stage = _current_stage(application)
    if stage is None:
        return Authority(False, "application_closed")
    if stage.status != ApplicationStage.Status.PENDING:
        return Authority(False, "already_decided")
    if _decided_this_cycle(user, application):
        return Authority(False, "already_decided")
    if acting_approver_id(application) != user.id:
        return Authority(False, "not_current_stage")
    return Authority(True, None)


@dataclass(frozen=True)
class ViewAccess:
    """A viewable application resolved for one approver."""

    stage_order: int
    role: str
    role_label: str
    stage: ApplicationStage | None = None


def get_view_access(user: User, application: LeaveApplication) -> ViewAccess | None:
    """The application's stage the user can review, or ``None`` (404).

    The user must be the assigned approver of at least one stage (of the live
    submission cycle) that is neither ``waiting`` nor ``skipped`` — i.e. the
    application must have reached them, or they must already have decided on it.
    A ``skipped`` stage was bypassed precisely so that its approver is not on the
    path (invariant 12.3 sole exception), so it confers no access.

    Unit 18: a Supervisor or HOD assigned to a cancellation stage may also read
    the approved application's review payload, even though the application is
    no longer ``submitted``. The ``stage`` of such a ``ViewAccess`` is ``None``.
    """
    from leave.cancellations.models import CancellationApprovalStage
    from .services import acting_approver_id

    live_stage = (
        application.stages.filter(
            submission_cycle=application.workflow_chain_cycle,
            status=ApplicationStage.Status.PENDING,
        )
        .first()
    )
    if live_stage is not None and acting_approver_id(application) == user.id:
        return ViewAccess(
            live_stage.stage_order, live_stage.role, live_stage.role_label, live_stage
        )

    stage = (
        application.stages.filter(
            assigned_approver=user,
            submission_cycle=application.workflow_chain_cycle,
        )
        .exclude(
            status__in=(
                ApplicationStage.Status.WAITING,
                # A bypassed stage is not a stage the application reached: its
                # approver was removed from the path, so they get no access.
                ApplicationStage.Status.SKIPPED,
            )
        )
        .first()
    )
    if stage is not None:
        return ViewAccess(stage.stage_order, stage.role, stage.role_label, stage)

    cancellation_stage = (
        CancellationApprovalStage.objects.filter(
            request__application=application,
            approver=user,
        )
        .exclude(status=CancellationApprovalStage.Status.NOT_REACHED)
        .order_by("order")
        .first()
    )
    if cancellation_stage is not None:
        return ViewAccess(
            cancellation_stage.order,
            cancellation_stage.role,
            cancellation_stage.role_label,
            None,
        )
    return None


def get_leave_history_scope(
    view_access: ViewAccess,
    employee_profile: EmployeeProfile | None,
    approver_profile: EmployeeProfile | None,
) -> tuple[bool, str]:
    """Resolve the leave-history subset visible to an approver.

    Returns ``(available, scope)`` where ``scope`` is ``all`` or
    ``current_financial_year``. Availability is conditional for HOD (same
    department) and Dean (same faculty/school); Registrar and DVC are always
    limited to the current financial year.
    """
    if view_access is None:
        return (False, "current_financial_year")
    if view_access.role == "supervisor":
        return (True, "all")
    if view_access.role == "hod":
        same = _same_profile_field(employee_profile, approver_profile, "department")
        return (same, "all")
    if view_access.role == "dean":
        same = _same_profile_field(employee_profile, approver_profile, "faculty")
        return (same, "all")
    return (True, "current_financial_year")


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
        submission_cycle=application.submission_cycle,
    ).exists()


def _current_stage(application: LeaveApplication) -> ApplicationStage | None:
    if application.current_stage_id is None:
        return None
    return ApplicationStage.objects.filter(pk=application.current_stage_id).first()