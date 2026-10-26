"""The "On Leave" read model: who may see whose approved leave.

One resolver and one payload builder, so every surface that answers "who is on
leave" answers it with the same scope. The scope is a ladder, and a viewer gets
the widest rung they stand on:

``organisation``   HR (and superusers) — every approved application.
``institution``    an institution-wide approver — the administration teams,
                   which is the half of the school an institution-wide office
                   serves (the same rule step staffing follows).
``campus``         a campus-wide approver — the teams at their own campus.
``team``           a designated team manager — the employees on the teams they
                   manage, across all of the team's chains.
``chain``          an ordinary team member — the people enrolled on the same
                   chain as them.
``self``           anyone else — their own approved leave only.

The chain rung is deliberately narrower than the team rung. A team routes one
or more chains at the same time, and its people are enrolled on them one at a
time (:class:`~chains.models.WorkflowMember`), so "my chain" is the chain the
person's own leave routes through (:mod:`chains.routing`) — not simply "my
team". Somebody nobody has enrolled routes through the team's default chain, so
they still see their colleagues rather than nobody.

Only *approved* applications are in scope anywhere: a submission still in
flight is the approvers' business, and a rejected or cancelled one is not leave
the organisation granted. Whose identity is attached to a row is never decided
here — the caller reads exactly the rows this module returns and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Q
from django.utils import timezone

from campuses.models import CampusRoleAssignment
from leave_types.models import LeaveType
from roles.models import RoleAssignment
from teams.models import Team
from users.models import EmployeeProfile

from .models import LeaveApplication

#: The six rungs of the visibility ladder, widest first as listed above.
ORGANISATION = "organisation"
INSTITUTION = "institution"
CAMPUS = "campus"
TEAM = "team"
CHAIN = "chain"
SELF = "self"

#: The longest free-text search the endpoint will run. HR's list is the only
#: one an unread search can be long on, and a name is short.
MAX_SEARCH_LENGTH = 100

#: How the viewer's own leave is described when they cover nobody else.
SELF_LABEL = "Your leave"


@dataclass(frozen=True)
class OnLeaveScope:
    """The employees whose approved leave ``user`` may read.

    ``employee_ids`` is ``None`` for HR's institution-wide rung — "no filter",
    not "nobody" — so a caller must branch on :meth:`covers_everyone` rather
    than treating ``None`` as an empty set.
    """

    kind: str
    label: str
    description: str
    employee_ids: frozenset[int] | None

    def covers_everyone(self) -> bool:
        return self.employee_ids is None

    def includes(self, user_id: int) -> bool:
        return self.employee_ids is None or user_id in self.employee_ids


def _profile_for(user) -> EmployeeProfile | None:
    """The user's employee record, read from the cache when it is already there."""
    profile = getattr(user, "employee_profile", None)
    if profile is not None:
        return profile
    return (
        EmployeeProfile.objects.filter(user=user)
        .select_related("team", "team__workflow")
        .first()
    )


def _team_member_ids(team_ids) -> set[int]:
    return set(
        EmployeeProfile.objects.filter(team_id__in=team_ids).values_list(
            "user_id", flat=True
        )
    )


def _institution_scope(user) -> OnLeaveScope | None:
    """The administration half of the school, for an institution-wide holder.

    Institution-wide offices serve administration teams — that is the rule the
    approver audit trail and step staffing already follow — so the same holding
    gives the same breadth here.
    """
    if not RoleAssignment.objects.filter(
        user=user,
        role__is_active=True,
        role__is_institution_wide=True,
    ).exists():
        return None
    ids = set(
        EmployeeProfile.objects.filter(
            team__category=Team.Category.ADMINISTRATION
        ).values_list("user_id", flat=True)
    )
    ids.add(user.pk)
    return OnLeaveScope(
        kind=INSTITUTION,
        label="Administration teams",
        description="Approved leave on the institution's administration teams.",
        employee_ids=frozenset(ids),
    )


def _campus_scope(user) -> OnLeaveScope | None:
    """The teams at the campuses where ``user`` holds a campus-wide role."""
    campuses = list(
        CampusRoleAssignment.objects.filter(user=user, role__is_active=True)
        .select_related("campus")
        .order_by("campus__name")
    )
    if not campuses:
        return None
    campus_ids = [row.campus_id for row in campuses]
    names = [row.campus.name for row in campuses]
    # A campus belongs to academic teams only (the model refuses a campus on an
    # administration team), so filtering on the campus is already the academic
    # half of that campus.
    ids = set(
        EmployeeProfile.objects.filter(team__campus_id__in=campus_ids).values_list(
            "user_id", flat=True
        )
    )
    ids.add(user.pk)
    label = ", ".join(names)
    return OnLeaveScope(
        kind=CAMPUS,
        label=label,
        description=f"Approved leave at {label}.",
        employee_ids=frozenset(ids),
    )


def _team_scope(user) -> OnLeaveScope | None:
    """Every employee on the teams ``user`` manages, across all their chains."""
    from roles.services import managed_team_ids_for

    team_ids = managed_team_ids_for(user)
    if not team_ids:
        return None
    names = list(
        Team.objects.filter(pk__in=team_ids)
        .order_by("name")
        .values_list("name", flat=True)
    )
    ids = _team_member_ids(team_ids)
    ids.add(user.pk)
    return OnLeaveScope(
        kind=TEAM,
        label=", ".join(names),
        description="Approved leave for the people on your team.",
        employee_ids=frozenset(ids),
    )


def _chain_scope(user, profile: EmployeeProfile | None) -> OnLeaveScope:
    """The people whose leave routes through the viewer's own chain.

    A team routes every chain its people are enrolled on at the same time, so
    "my chain" is decided per person (:mod:`chains.routing`) rather than by the
    team. The colleague set is read in one pass over the team's roster and
    enrolments, and a teammate the resolver places on a *different* chain of the
    same team is not in it — that is the whole point of the rung being narrower
    than the manager's.

    Somebody who is not enrolled on any chain still routes through the team's
    default chain, so they see their colleagues rather than nobody.
    """
    from chains.routing import routed_chain_ids_by_user
    from chains.routing import routed_workflow_for as _rwf

    chain = None
    if profile is not None and profile.team_id is not None:
        # Try routing first; if no enrolment, fall back to the team's default chain
 # for On Leave scope (the design says unenrolled people still see their colleagues).
        enrolled = _rwf(profile.team, user)
        if enrolled is None:
            # No enrolment - fall back to team's default chain
            default = profile.team.workflow
            if default is not None:
                chain = default
        else:
            chain = enrolled

    if chain is None:
        return _self_scope(user)

    ids = {user.pk}
    if chain.team_id is not None:
        routed = routed_chain_ids_by_user(chain.team)
        ids.update(
            user_id for user_id, chain_id in routed.items() if chain_id == chain.pk
        )
    return OnLeaveScope(
        kind=CHAIN,
        label=chain.name,
        description=f"Approved leave for the people on the {chain.name} chain.",
        employee_ids=frozenset(ids),
    )


def _self_scope(user) -> OnLeaveScope:
    return OnLeaveScope(
        kind=SELF,
        label=SELF_LABEL,
        description="Approved leave for your own applications.",
        employee_ids=frozenset({user.pk}),
    )


def resolve_scope(user) -> OnLeaveScope:
    """The widest On Leave scope ``user`` stands on.

    The order is the ladder, widest first, and the first rung that applies wins:
    HR covers everyone, an institution-wide holding covers the administration
    teams, a campus-wide holding covers its campus, a manager covers the teams
    they run, a chain member covers their chain, and everybody else covers
    themselves. A person may hold only one wide approver role, so the
    institution and campus rungs cannot both apply; the order still matters for
    HR, who may also be a manager.
    """
    if not getattr(user, "is_authenticated", False):
        return OnLeaveScope(
            kind=SELF,
            label=SELF_LABEL,
            description="Approved leave for your own applications.",
            employee_ids=frozenset(),
        )

    from roles.services import is_hr_actor

    if is_hr_actor(user):
        return OnLeaveScope(
            kind=ORGANISATION,
            label="Everyone",
            description="Approved leave across the institution.",
            employee_ids=None,
        )

    profile = _profile_for(user)
    for scope in (_institution_scope(user), _campus_scope(user), _team_scope(user)):
        if scope is not None:
            return scope
    return _chain_scope(user, profile)


def _state(application: LeaveApplication, today: date) -> str:
    """Where the leave sits relative to ``today``: on it, before it, or past it."""
    if application.start_date and application.start_date > today:
        return "upcoming"
    if application.end_date and application.end_date < today:
        return "returned"
    return "on_leave"


def _row(application: LeaveApplication, *, today: date, leave_types: dict) -> dict:
    """One payload row, with the employee's organisational context flattened.

    Names are read from the related rows loaded by the caller's
    ``select_related``; nothing here queries per row.
    """
    employee = application.employee
    profile = getattr(employee, "employee_profile", None)
    team = getattr(profile, "team", None) if profile is not None else None
    campus = getattr(team, "campus", None) if team is not None else None
    return {
        "id": str(application.pk),
        "reference_number": application.reference_number,
        "employee": {
            "id": employee.pk,
            "full_name": employee.get_full_name() or employee.username,
            "designation": profile.designation if profile is not None else "",
            "team": team.name if team is not None else "",
            "campus": campus.name if campus is not None else "",
        },
        "leave_type": {
            "id": application.leave_type_id,
            "name": leave_types.get(application.leave_type_id, ""),
        },
        "start_date": application.start_date.isoformat()
        if application.start_date
        else None,
        "end_date": application.end_date.isoformat() if application.end_date else None,
        "working_days": application.working_days,
        "state": _state(application, today),
    }


def on_leave_payload(
    *,
    user,
    include_past: bool = False,
    query: str = "",
    today: date | None = None,
) -> dict:
    """Approved leave within ``user``'s scope, shaped for the On Leave screen.

    ``today`` is injectable so a test can pin "who is on leave now" without
    depending on the wall clock. ``include_past`` adds returned leave after the
    current and upcoming rows — the screen's default is the answer to "who is
    away", not a leave archive. ``query`` filters on the employee's name or
    email and is ignored beyond :data:`MAX_SEARCH_LENGTH` characters.
    """
    scope = resolve_scope(user)
    today = today or timezone.localdate()

    base = LeaveApplication.objects.filter(
        status=LeaveApplication.Status.APPROVED,
        start_date__isnull=False,
        end_date__isnull=False,
    ).select_related(
        "employee",
        "employee__employee_profile",
        "employee__employee_profile__team",
        "employee__employee_profile__team__campus",
    )
    if not scope.covers_everyone():
        base = base.filter(employee_id__in=scope.employee_ids)

    search = (query or "").strip()[:MAX_SEARCH_LENGTH]
    if search:
        base = base.filter(
            Q(employee__first_name__icontains=search)
            | Q(employee__last_name__icontains=search)
            | Q(employee__email__icontains=search)
        )

    live = list(
        base.filter(end_date__gte=today).order_by(
            "start_date", "employee__first_name"
        )
    )
    returned = (
        list(
            base.filter(end_date__lt=today).order_by(
                "-end_date", "employee__first_name"
            )
        )
        if include_past
        else []
    )
    on_leave = [row for row in live if row.start_date and row.start_date <= today]
    upcoming = [row for row in live if row.start_date and row.start_date > today]

    leave_types = dict(
        LeaveType.objects.filter(
            pk__in={
                application.leave_type_id
                for application in live + returned
                if application.leave_type_id
            }
        ).values_list("id", "name")
    )

    results = [
        _row(application, today=today, leave_types=leave_types)
        for application in on_leave + upcoming + returned
    ]
    return {
        "today": today.isoformat(),
        "scope": {
            "kind": scope.kind,
            "label": scope.label,
            "description": scope.description,
        },
        "counts": {
            "on_leave": len(on_leave),
            "upcoming": len(upcoming),
            "returned": len(returned),
        },
        "results": results,
    }
