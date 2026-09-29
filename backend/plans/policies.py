"""Plan visibility and decision rules (Unit 25, D7/D16-D19).

The single source of truth for *who may view* a plan and its blocks:

* the **owner** always sees their own plan,
* a **stage approver** sees a plan once it has reached them or they decided
  (``waiting``/``skipped`` stages confer nothing), and
* **HR** sees every plan (settings/admin).

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
    scope: str  # "owner" | "approver" | "hr" | "peer" | "department"
    can_decide: bool = False


def _assigned_stage(user, plan: LeaveDayPlan) -> PlanApprovalStage | None:
    return (
        PlanApprovalStage.objects.filter(
            plan=plan,
            submission_cycle=plan.submission_cycle,
            assigned_approver=user,
        )
        .exclude(
            status__in=(
                PlanApprovalStage.Status.WAITING,
                PlanApprovalStage.Status.SKIPPED,
            )
        )
        .order_by("stage_order")
        .first()
    )


def plan_view_access(user: User, plan: LeaveDayPlan) -> PlanViewAccess | None:
    """The access ``user`` has to ``plan``, or ``None`` when it is a 404."""
    if plan.employee_id == user.pk:
        return PlanViewAccess(True, "owner")
    if user.role == User.Role.HR:
        return PlanViewAccess(True, "hr")
    stage = _assigned_stage(user, plan)
    if stage is not None:
        return PlanViewAccess(True, "approver", can_decide=True)
    return None


def user_is_approver(user: User) -> bool:
    """Approver roles (incl. HR) may use the plans approvals API."""
    from workflows.models import APPROVER_ROLE_CODES

    return bool(user) and user.role in APPROVER_ROLE_CODES


def department_scope(user: User) -> str | None:
    """The department label the user may review plans for, else ``None``.

    Supervisors/HODs and above (or any user who is someone's assigned
    supervisor) see their department's plans; HR sees all departments (D18).
    """
    profile = getattr(user, "employee_profile", None)
    if user.role == User.Role.HR:
        return "*"
    if user.role in ("supervisor", "hod", "dean", "registrar", "dvc"):
        return (profile.department or "").strip() or None
    if (
        profile is not None
        and profile.department
        and _supervises_anyone(user, (profile.department or "").strip())
    ):
        return (profile.department or "").strip()
    return None


def _supervises_anyone(user: User, department: str) -> bool:
    from users.models import EmployeeProfile

    return EmployeeProfile.objects.filter(
        supervisor=user,
        department__iexact=department,
    ).exists()