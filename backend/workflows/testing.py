"""Shared builders for approver-role, section, and routing test fixtures.

Routing used to be a property of ``User.role``, so a test could express "this
user is a supervisor" with one keyword argument. It is now a property of the
configuration tables, so expressing the same thing takes a role, a section, and
a membership row. This module is that one-liner, so tests stay readable and — more
importantly — so they build the *real* graph rather than a parallel one that could
drift from what the product actually does.

Three builders cover almost everything:

* :func:`make_approver` — one person holding one approver role, institution-wide.
  Enough for roles the routing tests resolve through ``RoleAssignment``.
* :func:`build_routing` — a full team with a workflow, a section per chain step,
  and a member per section, plus employees placed on the team. This is the shape
  :class:`~workflows.providers.DatabaseWorkflowProvider` reads, so it is what the
  database-provider tests should use.
* :func:`add_approver_to_section` — a *second* member on an existing section.
  A section is resolved by whoever acts first, so most routing tests want exactly
  one member and the interesting cases are the ones that add another.

All are idempotent on natural keys, so a ``setUp`` can call them freely.
"""

from django.contrib.auth import get_user_model

from users.models import EmployeeProfile

from .models import (
    ApproverRole,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    Workflow,
)

DEV_PASSWORD = "testpass123"

# The six shipped roles, with the behaviour each one carries. Mirrors the seed and
# migration 0011; kept here as data so a test can assert on exact values.
ROLE_SPECS = {
    "supervisor": {
        "label": "Supervisor",
        "history_scope": ApproverRole.HistoryScope.ALL,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "hod": {
        "label": "Head of Department",
        "history_scope": ApproverRole.HistoryScope.SAME_DEPARTMENT,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "dean": {
        "label": "Dean",
        "history_scope": ApproverRole.HistoryScope.SAME_FACULTY,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    "registrar": {
        "label": "Registrar",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "campus_registrar": {
        "label": "Campus Registrar",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "dvc": {
        "label": "Deputy Vice-Chancellor",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
}


def ensure_roles(*codes: str) -> dict[str, ApproverRole]:
    """Create the named approver roles and return them keyed by code.

    Defaults to all six. Inactive roles created by a previous test are reactivated
    so one test's deactivation cannot leak into the next.
    """
    wanted = codes or tuple(ROLE_SPECS)
    roles = {}
    for code in wanted:
        spec = ROLE_SPECS[code]
        role, _ = ApproverRole.objects.update_or_create(
            code=code,
            defaults={**spec, "is_active": True},
        )
        roles[code] = role
    return roles


def make_employee(
    username: str,
    *,
    department: str = "Administration",
    faculty: str = "Faculty of Science",
    category: str = EmployeeProfile.Category.ADMINISTRATION,
    team: Team | None = None,
    first_name: str = "Test",
    last_name: str = "Employee",
):
    """An ordinary employee, optionally already placed on a team."""
    User = get_user_model()
    user = User.objects.create_user(
        username=username,
        email=username,
        password=DEV_PASSWORD,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.EMPLOYEE,
    )
    EmployeeProfile.objects.create(
        user=user,
        department=department,
        faculty=faculty,
        category=category,
        grade="B",
        team=team,
    )
    return user


def make_approver(
    role_code: str,
    *,
    username: str | None = None,
    institution_wide: bool = True,
    roles: dict[str, ApproverRole] | None = None,
    **employee_kwargs,
):
    """A person holding one approver role, by default institution-wide.

    ``User.role`` is set to ``APPROVER`` for realism, but that value is *not* what
    makes them an approver — the :class:`RoleAssignment` row is. Tests that want
    to prove the distinction can set ``user.role`` back to ``EMPLOYEE``
    afterwards and assert they are still an approver.
    """
    User = get_user_model()
    roles = roles or ensure_roles(role_code)
    role = roles[role_code]
    username = username or f"approver-{role_code}@test.luanar"
    user = User.objects.create_user(
        username=username,
        email=username,
        password=DEV_PASSWORD,
        first_name="Test",
        last_name=role.label,
        role=User.Role.APPROVER,
    )
    EmployeeProfile.objects.create(
        user=user,
        department=employee_kwargs.pop("department", "Administration"),
        faculty=employee_kwargs.pop("faculty", "Faculty of Science"),
        category=employee_kwargs.pop("category", EmployeeProfile.Category.ADMINISTRATION),
        grade=employee_kwargs.pop("grade", "G"),
    )
    if institution_wide:
        role.is_institution_wide = True
        role.save(update_fields=["is_institution_wide"])
        RoleAssignment.objects.get_or_create(user=user, role=role)
    return user


def make_workflow(name: str, role_codes, *, is_active: bool = True) -> Workflow:
    """A workflow with one section per named role, in order.

    Sections are named after their role so the fixture reads the way the old
    ``WorkflowStage`` rows did; pass ``names`` to give them HR-style labels.
    """
    roles = ensure_roles(*role_codes)
    workflow, _ = Workflow.objects.update_or_create(
        name=name,
        defaults={
            "is_active": is_active,
            "effective_from": None,
        },
    )
    workflow.sections.all().delete()
    Section.objects.bulk_create(
        [
            Section(
                workflow=workflow,
                order=index,
                name=roles[code].label,
                approver_role=roles[code],
            )
            for index, code in enumerate(role_codes, start=1)
        ]
    )
    return workflow


def make_section(workflow, order: int, role_code: str, *, name: str | None = None):
    """One section on ``workflow``, resolving ``role_code`` to its role row."""
    role = ensure_roles(role_code)[role_code]
    section, _ = Section.objects.update_or_create(
        workflow=workflow,
        order=order,
        defaults={"name": name or role.label, "approver_role": role},
    )
    return section


def make_stage(workflow, order: int, role_code: str):
    """Backwards-compatible alias for :func:`make_section`.

    Tests that read "the second stage" are describing the same thing a section
    is now; keeping the old name would mean two vocabularies for one concept, so
    the old name stays only until the call sites are updated.
    """
    return make_section(workflow, order, role_code)


def add_approver_to_section(section, role_code: str, *, user=None):
    """Put one more person on ``section`` so it has several possible approvers.

    This is the capability sections exist for: a step two people may act on. The
    second member is a *set* addition, not a replacement, so the section still
    routes to whoever the test built first.
    """
    roles = ensure_roles(role_code)
    user = user or make_approver(role_code, roles=roles, institution_wide=False)
    SectionMember.objects.get_or_create(section=section, user=user)
    return user


def make_team(
    name: str,
    role_codes,
    *,
    code: str | None = None,
    approvers: dict[str, object] | None = None,
    workflow: Workflow | None = None,
    status: str = Team.Status.ACTIVE,
    department: str = "",
    effective_from=None,
    effective_to=None,
    employees=(),
) -> Team:
    """A team routed by ``workflow``, with the named roles staffed.

    ``approvers`` maps a role code to a user, for tests that need the approver to
    be a specific person. Roles not named fall back to
    :func:`make_approver` with the conventional username.

    ``role_codes`` says which sections to staff, and it does **not** have to
    cover the whole workflow. A section whose role is not listed is left with no
    member, which is how a test reaches the institution-wide fallback, or a
    section with nobody to act for it. Use :func:`add_approver_to_section` to put
    a second person on one of the sections built here.

    ``status`` defaults to active because a team that cannot route is a special
    case, not the default state of a routing fixture. The model itself defaults
    to draft; tests that are about configuration rather than routing pass
    ``Team.Status.DRAFT`` explicitly.
    """
    roles = ensure_roles(*role_codes)
    workflow = workflow or make_workflow(f"{name} Workflow", role_codes)
    team, _ = Team.objects.update_or_create(
        name=name,
        defaults={
            "code": code or name.lower().replace(" ", "-"),
            "workflow": workflow,
            "status": status,
            "department": department,
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )
    wanted = set(role_codes)
    sections = [
        section
        for section in team.workflow.sections.order_by("order").select_related(
            "approver_role"
        )
        if section.approver_role.code in wanted
    ]
    for section in sections:
        role_code = section.approver_role.code
        user = (approvers or {}).get(role_code)
        if user is None:
            user = make_approver(role_code, roles=roles)
        SectionMember.objects.get_or_create(section=section, user=user)
    for employee in employees:
        profile = EmployeeProfile.objects.filter(user=employee).first()
        if profile is None:
            EmployeeProfile.objects.create(
                user=employee, department="Administration", grade="B", team=team
            )
        else:
            profile.team = team
            profile.save(update_fields=["team"])
    return team


def build_routing(
    *,
    employee=None,
    employee_username: str = "employee@test.luanar",
    chain=("supervisor", "hod", "registrar", "dvc"),
    approvers: dict[str, object] | None = None,
    institution_wide_roles=("registrar",),
    team_name: str = "Test Team",
    status: str = Team.Status.ACTIVE,
):
    """A complete, routable configuration in one call.

    Builds a workflow over ``chain``, a team holding a member per role, and — for
    each role in ``institution_wide_roles`` — an institution-wide holder instead of
    a team membership. That mix is what exercises both branches of the resolution
    rule: a team member for ``supervisor``/``hod``, and a global holder for
    ``registrar``.

    Returns ``(employee, team, roles)``.
    """
    roles = ensure_roles(*chain)
    workflow = make_workflow(f"{team_name} Workflow", chain)
    for role_code in institution_wide_roles:
        if role_code in roles:
            roles[role_code].is_institution_wide = True
            roles[role_code].save(update_fields=["is_institution_wide"])

    team = make_team(
        team_name,
        [code for code in chain if code not in institution_wide_roles],
        workflow=workflow,
        approvers=approvers,
        status=status,
    )
    for role_code in institution_wide_roles:
        user = (approvers or {}).get(role_code)
        if user is None:
            user = make_approver(
                role_code, roles=roles, institution_wide=True
            )
        RoleAssignment.objects.get_or_create(user=user, role=roles[role_code])

    employee = employee or make_employee(employee_username)
    profile = EmployeeProfile.objects.filter(user=employee).first()
    if profile is None:
        EmployeeProfile.objects.create(
            user=employee, department="Administration", grade="B", team=team
        )
    else:
        profile.team = team
        profile.save(update_fields=["team"])
    return employee, team, roles


# The approver codes the pre-migration ``User.Role`` enum used. Tests pass one of
# these as ``role`` and :func:`create_user_with_role` turns it into a real
# ``ApproverRole`` plus an institution-wide holding, which is what actually makes
# somebody an approver. Keeping the codes in the test vocabulary means a test
# reads "make me a hod" without each file re-implementing the mapping.
APPROVER_ROLE_CODES = frozenset(ROLE_SPECS)


def grant_approver_role(user, role_code: str, *, institution_wide: bool = True):
    """Give ``user`` the named approver role and return the role row.

    Institution-wide by default, because a test that only wants "this person
    approves" should not also have to invent a team. Tests that care about
    team-scoped resolution pass ``institution_wide=False`` and add their own
    ``TeamMember``.
    """
    role = ensure_roles(role_code)[role_code]
    if institution_wide:
        if not role.is_institution_wide:
            role.is_institution_wide = True
            role.save(update_fields=["is_institution_wide"])
        RoleAssignment.objects.get_or_create(user=user, role=role)
    return role


def create_user_with_role(username: str, *, role, **kwargs):
    """``create_user`` that understands approver codes.

    ``role`` may be any :class:`~users.models.User.Role` value *or* one of the six
    approver role codes. In the latter case the account is created with
    ``User.Role.APPROVER`` and given a real role holding, so
    :func:`workflows.services.is_approver_user` agrees with the test's intent
    without every test having to build a team.
    """
    User = get_user_model()
    if isinstance(role, str) and role in APPROVER_ROLE_CODES:
        user = User.objects.create_user(
            username=username,
            email=kwargs.pop("email", username),
            password=kwargs.pop("password", DEV_PASSWORD),
            role=User.Role.APPROVER,
            **kwargs,
        )
        grant_approver_role(user, role)
        return user
    return User.objects.create_user(
        username=username,
        email=kwargs.pop("email", username),
        password=kwargs.pop("password", DEV_PASSWORD),
        role=role,
        **kwargs,
    )
