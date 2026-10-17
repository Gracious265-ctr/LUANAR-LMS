"""Domain logic for Leave Plans (refinement unit 04).

Three concerns live here, in the order a plan moves through them:

* :func:`create_plan` / :func:`update_plan` — validate that the type is
  plannable and that the range does not silently duplicate existing intent.
* :func:`convert_plan_to_draft` — the "Apply Now" handoff. It delegates to the
  Leave app's own draft-creation path so a plan-built draft is byte-for-byte the
  draft the employee would have created by hand.
* :func:`resolve_scopes` / :func:`plans_for_scope` — the assignment-driven team
  calendar. There is no org-unit table: a person's visible teams are derived from
  their ``EmployeeProfile.team`` plus any ``TeamRoleAssignment``,
  ``CampusRoleAssignment`` or institution-wide ``RoleAssignment`` they hold.

The overlap check is deliberately a *warning*, not a guard: the same dates may be
planned twice by accident, and the employee is the only one who can say whether
they meant to. Nothing here ever writes to the approval workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from leave.models import LeaveApplication, LeaveType
from leave.services import create_draft_application
from users.models import EmployeeProfile
from workflows.models import CampusRoleAssignment, RoleAssignment, Team, TeamRoleAssignment

from .models import LeavePlan, LeavePlanStatus


class PlanError(Exception):
    """Base class for Leave Plan rule violations surfaced to the API."""


class LeaveTypeNotPlannableError(PlanError):
    """Raised when a plan names a leave type HR has marked non-plannable."""


class PlanAlreadyConvertedError(PlanError):
    """Raised when a terminal plan is asked to convert a second time."""


class PlanConvertedError(PlanError):
    """Raised when a converted/cancelled/missed plan is edited or applied to."""


def _open_plans(employee) -> QuerySet[LeavePlan]:
    """Plans still in play for an employee (the ones overlap can matter for)."""
    return LeavePlan.objects.filter(
        employee=employee,
        status__in=(LeavePlanStatus.UPCOMING, LeavePlanStatus.NOTIFIED),
    )


def find_plan_overlap(
    *, employee, start_date: date, end_date: date, exclude_plan_id=None
) -> str | None:
    """Return a human warning when the range overlaps existing intent, else None.

    Two sources count as "intent": the employee's still-open plans and any leave
    application that is neither cancelled nor rejected. The message is advisory —
    callers always allow the plan through.
    """
    plans = _open_plans(employee)
    if exclude_plan_id is not None:
        plans = plans.exclude(pk=exclude_plan_id)
    plan_hit = plans.filter(
        planned_start_date__lte=end_date, planned_end_date__gte=start_date
    ).first()
    if plan_hit is not None:
        return (
            f"This overlaps with an existing plan for {plan_hit.leave_type.name} "
            f"({plan_hit.planned_start_date}–{plan_hit.planned_end_date})."
        )

    application_hit = (
        LeaveApplication.objects.filter(employee=employee)
        .exclude(
            status__in=(
                LeaveApplication.Status.CANCELLED,
                LeaveApplication.Status.REJECTED,
            )
        )
        .filter(start_date__lte=end_date, end_date__gte=start_date)
        .first()
    )
    if application_hit is not None:
        return (
            f"This overlaps with an existing {application_hit.get_status_display().lower()} "
            "leave application for the same dates."
        )
    return None


def _assert_plannable(leave_type: LeaveType) -> None:
    if not leave_type.plannable:
        raise LeaveTypeNotPlannableError(
            f"{leave_type.name} cannot be planned. Choose a leave type that "
            "allows planning."
        )


@transaction.atomic
def create_plan(
    *,
    employee,
    leave_type: LeaveType,
    financial_year,
    start_date: date,
    end_date: date,
    notes: str = "",
) -> tuple[LeavePlan, str | None]:
    """Create an open plan. Returns the plan and any overlap warning."""
    _assert_plannable(leave_type)
    warning = find_plan_overlap(
        employee=employee, start_date=start_date, end_date=end_date
    )
    plan = LeavePlan.objects.create(
        employee=employee,
        leave_type=leave_type,
        financial_year=financial_year,
        planned_start_date=start_date,
        planned_end_date=end_date,
        notes=notes,
    )
    return plan, warning


@transaction.atomic
def update_plan(
    *,
    plan: LeavePlan,
    leave_type: LeaveType,
    financial_year,
    start_date: date,
    end_date: date,
    notes: str,
) -> tuple[LeavePlan, str | None]:
    """Edit an open plan in place. Returns the plan and any overlap warning."""
    if not plan.is_actionable:
        raise PlanConvertedError("A plan that is no longer open cannot be edited.")
    _assert_plannable(leave_type)
    warning = find_plan_overlap(
        employee=plan.employee,
        start_date=start_date,
        end_date=end_date,
        exclude_plan_id=plan.pk,
    )
    plan.leave_type = leave_type
    plan.financial_year = financial_year
    plan.planned_start_date = start_date
    plan.planned_end_date = end_date
    plan.notes = notes
    plan.save(
        update_fields=[
            "leave_type",
            "financial_year",
            "planned_start_date",
            "planned_end_date",
            "notes",
            "updated_at",
        ]
    )
    return plan, warning


@transaction.atomic
def convert_plan_to_draft(*, plan: LeavePlan) -> LeaveApplication:
    """Turn an open plan into a Leave draft through the standard draft path.

    Idempotent: a plan already handed off returns its converted draft rather than
    creating a second one. The financial-year and balance rules are *not* applied
    here — they belong to submission, which the employee still has to go through.
    """
    if plan.status == LeavePlanStatus.CONVERTED and plan.converted_application:
        return plan.converted_application
    if not plan.is_actionable:
        raise PlanConvertedError("A cancelled, missed or converted plan cannot be applied for.")

    application = create_draft_application(
        employee=plan.employee,
        leave_type=plan.leave_type,
        start_date=plan.planned_start_date,
        end_date=plan.planned_end_date,
        reason=plan.notes,
        source_plan=plan,
    )
    plan.status = LeavePlanStatus.CONVERTED
    plan.converted_application = application
    plan.save(update_fields=["status", "converted_application", "updated_at"])
    return application


@transaction.atomic
def cancel_plan(*, plan: LeavePlan) -> LeavePlan:
    """Cancel an open plan. Idempotent for a plan already cancelled."""
    if plan.status in (LeavePlanStatus.CONVERTED, LeavePlanStatus.CANCELLED):
        return plan
    plan.status = LeavePlanStatus.CANCELLED
    plan.save(update_fields=["status", "updated_at"])
    return plan


@dataclass(frozen=True)
class PlanScope:
    """One selectable calendar scope: a token, a label and the teams it spans."""

    token: str
    label: str
    team_ids: frozenset[int]


def _team_scope(team: Team) -> PlanScope:
    return PlanScope(token=f"team:{team.pk}", label=team.name, team_ids=frozenset({team.pk}))


def resolve_scopes(user) -> list[PlanScope]:
    """Return the calendar scopes ``user`` may view, narrowest first.

    Assignment-driven, never role-name-driven (Decision 2): the visible teams are
    whatever the person's profile and assignments say they belong to. The first
    entry is therefore the narrowest — a section member sees their own team, a
    campus registrar their whole campus, an institution-wide officer everything.
    """
    scopes: list[PlanScope] = []
    seen: set[str] = set()

    def add(scope: PlanScope | None) -> None:
        if scope is not None and scope.token not in seen:
            seen.add(scope.token)
            scopes.append(scope)

    profile = EmployeeProfile.objects.filter(user=user).select_related("team").first()
    if profile is not None and profile.team_id is not None:
        add(_team_scope(profile.team))

    for assignment in TeamRoleAssignment.objects.filter(user=user).select_related("team"):
        add(_team_scope(assignment.team))

    for assignment in CampusRoleAssignment.objects.filter(user=user).select_related("campus"):
        team_ids = frozenset(
            Team.objects.filter(campus_id=assignment.campus_id).values_list("pk", flat=True)
        )
        add(
            PlanScope(
                token=f"campus:{assignment.campus_id}",
                label=f"{assignment.campus.name} campus",
                team_ids=team_ids,
            )
        )

    if RoleAssignment.objects.filter(user=user).exists():
        team_ids = frozenset(Team.objects.values_list("pk", flat=True))
        add(PlanScope(token="institution", label="Whole institution", team_ids=team_ids))

    # Narrowest first: a one-team scope is always more specific than a campus or
    # institution scope, and stable ordering keeps the default deterministic.
    scopes.sort(key=lambda scope: (len(scope.team_ids), scope.label.casefold()))
    return scopes


def default_scope(user) -> PlanScope | None:
    """The narrowest scope a user belongs to, or None when they belong to none."""
    scopes = resolve_scopes(user)
    return scopes[0] if scopes else None


def find_scope(user, token: str | None) -> PlanScope | None:
    """Resolve a requested scope token against ``user``'s allowed scopes.

    A missing token means "use my default"; an unknown token returns None so the
    view can 404 rather than leaking whether the scope exists.
    """
    scopes = resolve_scopes(user)
    if not scopes:
        return None
    if token is None:
        return scopes[0]
    for scope in scopes:
        if scope.token == token:
            return scope
    return None


def plans_for_scope(scope: PlanScope, month_start: date, month_end: date) -> QuerySet[LeavePlan]:
    """Open-and-active plans for the members of ``scope`` in a date window.

    Converted plans drop out — they are now real applications and belong on the
    leave calendar, not the planning one — as do cancelled ones. Missed plans
    stay visible so a team can see a window that came and went unactioned.
    """
    if not scope.team_ids:
        return LeavePlan.objects.none()
    member_ids = EmployeeProfile.objects.filter(
        team_id__in=scope.team_ids
    ).values_list("user_id", flat=True)
    return (
        LeavePlan.objects.filter(
            employee_id__in=member_ids,
            status__in=(
                LeavePlanStatus.UPCOMING,
                LeavePlanStatus.NOTIFIED,
                LeavePlanStatus.MISSED,
            ),
            planned_start_date__lte=month_end,
            planned_end_date__gte=month_start,
        )
        .select_related("employee", "leave_type")
        .order_by("planned_start_date", "employee__first_name")
    )


def mark_missed_plans(*, as_of: date | None = None) -> int:
    """Flip notified/upcoming plans whose window has passed to ``missed``.

    Called by the daily job. A plan whose end date is before ``as_of`` and which
    was never converted is history the employee did not act on; marking it keeps
    the open list honest. Returns the number of rows moved.
    """
    as_of = as_of or timezone.localdate()
    return _open_plans_all().filter(planned_end_date__lt=as_of).update(
        status=LeavePlanStatus.MISSED
    )


def _open_plans_all() -> QuerySet[LeavePlan]:
    return LeavePlan.objects.filter(
        status__in=(LeavePlanStatus.UPCOMING, LeavePlanStatus.NOTIFIED)
    )
