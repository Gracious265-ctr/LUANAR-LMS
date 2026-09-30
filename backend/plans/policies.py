"""Plan visibility and decision rules (Unit 25, D7/D16-D19).

The single source of truth for *who may view* a plan and its blocks:

* the **owner** always sees their own plan,
* somebody **entitled to act** on it sees a plan once it has reached them — that
  is, they are in the live stage's eligibility snapshot, or they are the
  delegate of somebody who is, or they have already taken up a stage on it —
  and **HR** sees every plan (settings/admin).

A ``waiting`` stage confers nothing: you cannot see a plan because you might
act on it later. Authority is read from the stage's snapshot, never from
``User.role`` and never from holding the same role in some other team's
configuration.

Decision authority itself is enforced under row locks inside
:func:`plans.services.decide_plan`; the dataclass here is the lightweight
counterpart used by the API for early capability hints.
"""

from __future__ import annotations

from dataclasses import dataclass

from users.models import User

from .models import LeaveDayPlan, PlanApprovalStage


@dataclass(frozen=True)
class PlanViewAccess:
    """Whether ``user`` may view a plan, and their relationship to it."""

    can_view: bool
    scope: str  # "owner" | "approver" | "hr"
    can_decide: bool = False


def user_is_hr(user: User) -> bool:
    """Whether ``user`` holds HR's blanket oversight.

    ``User.role`` is the right question *here* and only here: HR is a system
    access level, not a place in an approval chain. Approval authority never
    reads it.
    """
    return bool(user) and user.role == User.Role.HR


def _acted_stage(user, plan: LeaveDayPlan) -> bool:
    """Whether ``user`` has taken up a decided stage on ``plan``.

    Once somebody acts the stage records them in ``assigned_approver``, so a
    colleague who was eligible at the time but lost the race still keeps sight of
    the plan they were asked to review — without that, the decided tab of the
    queue would be empty for them and they would have no record of what they
    were asked to do.
    """
    return plan.approval_stages.filter(
        plan=plan,
        submission_cycle=plan.submission_cycle,
        assigned_approver=user,
    ).exclude(status=PlanApprovalStage.Status.WAITING).exists()


def plan_view_access(user: User, plan: LeaveDayPlan) -> PlanViewAccess | None:
    """The access ``user`` has to ``plan``, or ``None`` when it is a 404.

    ``can_decide`` is a *hint* for the UI only; the authoritative check runs
    under a row lock in :func:`plans.services.decide_plan`.
    """
    from .services import acting_approver_ids, eligible_approver_ids

    if plan.employee_id == user.pk:
        return PlanViewAccess(True, "owner")
    if user_is_hr(user):
        return PlanViewAccess(True, "hr")

    eligible = eligible_approver_ids(plan)
    if user.pk in acting_approver_ids(plan, eligible):
        return PlanViewAccess(True, "approver", can_decide=True)
    if _acted_stage(user, plan):
        return PlanViewAccess(True, "approver")
    return None


def user_is_approver(user: User) -> bool:
    """Whether ``user`` may use the plans approvals API.

    Delegated from the workflows app so "is an approver" has exactly one
    definition: holding at least one active approver role, as a section member or
    as an institution-wide role assignee.
    """
    from workflows.services import is_approver_user

    return is_approver_user(user)


def team_member_ids(user: User) -> list[int]:
    """The other active members of ``user``'s own team.

    The plan equivalent of "my peers". An employee with no team has no team view,
    which the API reports rather than silently falling back to the whole
    department.
    """
    from users.models import EmployeeProfile

    profile = getattr(user, "employee_profile", None)
    if profile is None or profile.team_id is None:
        return []
    return list(
        EmployeeProfile.objects.filter(
            user__is_active=True,
            team_id=profile.team_id,
        )
        .exclude(user_id=user.pk)
        .values_list("user_id", flat=True)
    )


def department_member_ids(user: User) -> list[int]:
    """Everyone in the *department* of ``user``'s team, other than ``user``.

    Department is a property of the team now — it is the free-text label on
    ``Team.department`` — so a department-wide review spans every team in that
    department rather than every profile that happens to share a string.
    """
    from users.models import EmployeeProfile

    profile = getattr(user, "employee_profile", None)
    if profile is None or profile.team_id is None:
        return []
    department = (profile.team.department or "").strip()
    if not department:
        return []
    return list(
        EmployeeProfile.objects.filter(
            user__is_active=True,
            team__department__iexact=department,
        )
        .exclude(user_id=user.pk)
        .values_list("user_id", flat=True)
    )
