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
  and an approver per section, plus employees placed on the team. This is the
  shape :class:`~workflows.providers.DatabaseWorkflowProvider` reads, so it is
  what the database-provider tests should use.
* :func:`appoint_approver_to_section` — appoint or replace the one approver of an
  existing step. A step has a single approver, so this closes the previous
  holder's period rather than adding a second person beside them.

All are idempotent on natural keys, so a ``setUp`` can call them freely.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from users.models import EmployeeProfile

from organisation.models import ApproverRole, Campus, RoleAssignment, Team
from workflows.models import Section, SectionMember, Workflow, WorkflowMember

DEV_PASSWORD = "testpass123"


def campus_for(name: str | None) -> Campus | None:
    """Resolve a campus *name* to the row, creating it if needed.

    Campuses are shared reference data, so each builder resolves the name here
    rather than making every caller do it — which also stops two tests quietly
    creating two "Main Campus" rows.

    A blank or missing name resolves to ``None``, which the models allow: it is
    how a fixture expresses "this team is not campus-based".
    """
    if not name:
        return None
    campus, _ = Campus.objects.get_or_create(
        name=name, defaults={"code": name.lower().replace(" ", "-")}
    )
    return campus


def team_for(name: str) -> Team:
    """Resolve a team *name* to the row, creating a bare one if needed.

    Exists for the same reason as :func:`campus_for`: fixtures that only need an
    employee to be *on* a team should not have to describe that team's whole
    approval configuration. The team created here has no workflow and so cannot
    route — which is exactly right for a fixture about membership rather than
    routing.
    """
    team, _ = Team.objects.get_or_create(
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": Team.Status.ACTIVE},
    )
    return team


# The six shipped roles, with the behaviour each one carries. Mirrors what
# migration 0011 used to seed, kept here as data so tests can assert on exact
# values and so a bare test database does not depend on migration seed rows.
ROLE_SPECS = {
    "supervisor": {
        "label": "Supervisor",
        "description": "Line manager of the applicant.",
        "history_scope": ApproverRole.HistoryScope.ALL,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "hod": {
        "label": "Head of Department",
        "description": "Head of the applicant's department.",
        "history_scope": ApproverRole.HistoryScope.SAME_TEAM,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "dean": {
        "label": "Dean",
        "description": "Dean of the applicant's faculty.",
        "history_scope": ApproverRole.HistoryScope.SAME_FACULTY,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    "registrar": {
        "label": "Registrar",
        "description": "Institution-wide registrar; approves every application.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "campus_registrar": {
        "label": "Campus Registrar",
        "description": "Registrar for a single campus.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "dvc": {
        "label": "Deputy Vice-Chancellor",
        "description": "Deputy Vice-Chancellor; final institution-wide approval.",
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
    team: Team | None = None,
    team_name: str | None = None,
    faculty: str = "Faculty of Science",
    category: str = EmployeeProfile.Category.ADMINISTRATION,
    first_name: str = "Test",
    last_name: str = "Employee",
):
    """An ordinary employee, optionally already placed on a team.

    The team is the employee's whole organisational identity: it is what scopes
    their approver eligibility and what selects the workflow their applications
    route through. Pass ``team`` for a team the caller already has, or ``team_name``
    to have a bare one created here.
    """
    User = get_user_model()
    user = User.objects.create_user(
        username=username,
        email=username,
        password=DEV_PASSWORD,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.EMPLOYEE,
    )
    if team is None and team_name:
        team = team_for(team_name)
    EmployeeProfile.objects.create(
        user=user,
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
    team: Team | None = None,
    roles: dict[str, ApproverRole] | None = None,
    **employee_kwargs,
):
    """A person holding one approver role, by default institution-wide.

    Idempotent on the username: a repeated call returns the same person rather
    than colliding on ``users_user_username_key``. Several tests build more than
    one team with the same roles, and each team needs its own approver on it, so
    the *caller* passes a distinct ``username`` when it needs a distinct person —
    which is exactly the distinction it is trying to express.

    ``institution_wide=False`` makes this a team-scoped approver, so the person is
    placed on ``team`` — a team-scoped approver who is not a team member could not
    be appointed by a real write, so a fixture must not build one.

    ``User.role`` is set to ``APPROVER`` for realism, but that value is *not* what
    makes them an approver — the :class:`RoleAssignment` row is, or a section
    appointment. Tests that want to prove the distinction can set ``user.role``
    back to ``EMPLOYEE`` afterwards and assert they are still an approver.
    """
    User = get_user_model()
    roles = roles or ensure_roles(role_code)
    role = roles[role_code]
    username = username or f"approver-{role_code}@test.luanar"
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create_user(
            username=username,
            email=username,
            password=DEV_PASSWORD,
            first_name="Test",
            last_name=role.label,
            role=User.Role.APPROVER,
        )
    profile, _ = EmployeeProfile.objects.update_or_create(
        user=user,
        defaults={
            "faculty": employee_kwargs.pop("faculty", "Faculty of Science"),
            "category": employee_kwargs.pop(
                "category", EmployeeProfile.Category.ADMINISTRATION
            ),
            "grade": employee_kwargs.pop("grade", "G"),
        },
    )
    if not institution_wide and team is not None:
        profile.team = team
        profile.save(update_fields=["team"])
    assert profile is not None
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


def appoint_approver_to_section(section, role_code: str, *, user=None, team=None):
    """Appoint one person as ``section``'s approver and record the period.

    The step has exactly one approver, so this is a *replacement* when the step
    already had one: the outgoing person's period is closed rather than left open
    alongside the new one. The same relationship the API's add-member action
    writes — ``Section.approver`` plus the ``SectionMember`` record — is written
    here, so fixtures exercise the real graph.

    A built approver is placed on the section's own team, so the appointment
    passes the same membership rule a real write would.
    """
    roles = ensure_roles(role_code)
    if user is None:
        if team is None:
            team = getattr(section.workflow, "team", None)
        user = make_approver(
            role_code, roles=roles, institution_wide=False, team=team
        )
    previous = section.approver
    if previous is not None and previous.pk != user.pk:
        SectionMember.objects.filter(
            section=section, user=previous, effective_to__isnull=True
        ).update(effective_to=timezone.localdate())
    section.approver = user
    section.save(update_fields=["approver"])
    SectionMember.objects.update_or_create(
        section=section,
        user=user,
        effective_to__isnull=True,
        defaults={"effective_from": timezone.localdate()},
    )
    return user


def make_team(
    name: str,
    role_codes,
    *,
    code: str | None = None,
    approvers: dict[str, object] | None = None,
    workflow: Workflow | None = None,
    status: str = Team.Status.ACTIVE,
    campus: str | None = None,
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
    approver, which is how a test reaches the institution-wide fallback, or a
    step with nobody to act for it. Use :func:`appoint_approver_to_section` to
    appoint somebody to one of the sections built here.

    Approvers are built *on the team* because a team-scoped approver must be a
    member of the team they approve for — the same rule a real write enforces, so
    a fixture cannot build a team that the product would refuse.

    ``status`` defaults to active because a team that cannot route is a special
    case, not the default state of a routing fixture. The model itself defaults
    to draft; tests that are about configuration rather than routing pass
    DRAFT status is no longer used; all teams are active by default.
    """
    roles = ensure_roles(*role_codes)
    workflow = workflow or make_workflow(f"{name} Workflow", role_codes)
    # Ownership is part of the fixture, not a separate thing a test has to
    # remember: the chain this team routes through is also the chain this team
    # owns, which is what the team's workflow screens read.
    team, _ = Team.objects.update_or_create(
        name=name,
        defaults={
            "code": code or name.lower().replace(" ", "-"),

            "status": status,
            # A campus and a category always agree here, the same way they do
            # on a real write: a team that sits at a campus is academic, and a
            # team that does not is institution-wide.
            "category": (
                Team.Category.ACADEMIC
                if campus
                else Team.Category.ADMINISTRATION
            ),
            "campus": campus_for(campus),
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )
    if workflow.team_id is None:
        workflow.team = team
        workflow.save(update_fields=["team"])
    wanted = set(role_codes)
    sections = [
        section
        for section in workflow.sections.order_by("order").select_related(
            "approver_role"
        )
        if section.approver_role.code in wanted
    ]
    for section in sections:
        role_code = section.approver_role.code
        user = (approvers or {}).get(role_code)
        if user is None:
            # The username carries the team so two teams in one test get two
            # different people: one approver may hold one role per team, and two
            # teams would otherwise appoint the same fixture user twice and
            # quietly share an approver.
            user = make_approver(
                role_code,
                username=f"approver-{team.code}-{role_code}@test.luanar",
                roles=roles,
                institution_wide=False,
                team=team,
            )
        appoint_approver_to_section(section, role_code, user=user)
    for employee in employees:
        profile = EmployeeProfile.objects.filter(user=employee).first()
        if profile is None:
            EmployeeProfile.objects.create(
                user=employee, grade="B", team=team
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
            user=employee, grade="B", team=team
        )
    else:
        profile.team = team
        profile.save(update_fields=["team"])
    # Routing follows membership, not team placement: the applicant follows the
    # chain they are enrolled in, so a routable fixture enrols them in it.
    WorkflowMember.objects.get_or_create(team=team, workflow=workflow, user=employee)
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
