"""Workflow and team lifecycle: create, edit, route, and retire.

A *team* is the organisational unit that owns one or more approval chains and is
put in force when HR creates it; a *workflow* is one of the chains it owns. A
team routes every chain its people are enrolled on at the same time, and the
chain named as the team's :attr:`~teams.models.Team.workflow` is the **default**
one — where somebody not yet placed on one of the team's chains routes, and where
a wide approver routes when their holding staffs several. This module owns the
two lifecycles and the readiness check that reports — without mutating anything
— whether a team can route an application today.

Chain *structure* (validating and rewriting a step list) lives in
:mod:`workflows.services.configuration`; appointing the people who staff those
steps goes through :mod:`workflows.services.membership`, so a chain written
inline with a team is held to exactly the same rules as one edited on its own
screen.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from leave.services import active_financial_year
from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment
from roles.services import (
    _require_hr_actor,
    create_team_role_assignment,
)
from teams.models import Team, TeamRoleAssignment
from users.models import User
from chains.models import Section, SectionMember, Workflow, WorkflowMember
from chains.providers import WorkflowConfigError, resolve_section_approvers
from chains.services import _shared
from chains.services._shared import (
    TeamActionError,
    TeamIssue,
    TeamReadiness,
    WorkflowActionError,
    _require_can_manage_team,
    _unique_team_code,
    _unique_workflow_name,
)
from chains.services.configuration import (
    StageSequenceError,
    _workflow_snapshot,
    replace_workflow_sections,
)
from chains.services.membership import (
    _team_name,
    add_section_member,
    ensure_membership_allowed,
    holds_role_wide_for_team,
    sync_workflow_members,
)


def wide_holder_ids(team: Team, role: ApproverRole) -> set[int]:
    """Everyone who can staff ``role`` for ``team`` without an appointment.

    The set :func:`validate_team` needs to tell "this approver is outside the
    team, which is a problem" from "this approver is outside the team, which is
    the point of a wide holding". Scoped exactly as resolution is: the team's own
    holder, the holder at the team's campus, and — for an administration team —
    the institution-wide holder.
    """
    ids = set(
        TeamRoleAssignment.objects.filter(
            team=team, role=role, user__is_active=True
        ).values_list("user_id", flat=True)
    )
    if team.campus_id is not None and team.category == Team.Category.ACADEMIC:
        ids |= set(
            CampusRoleAssignment.objects.filter(
                campus_id=team.campus_id, role=role, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    if role.is_institution_wide and team.category == Team.Category.ADMINISTRATION:
        ids |= set(
            RoleAssignment.objects.filter(
                role=role, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    return ids


def validate_team(team: Team) -> TeamReadiness:
    """Check whether a team can route an application's approvals.

    Side-effect free and safe to call at any time. A team is in force from
    creation, so this is a *standing* check rather than a gate before an
    activation: it is how HR finds the step that has lost its approver since the
    chain was written, and reports a team that has nothing to route through.

    Every chain the team routes is checked, not only its default one: a team
    routes one or more chains at the same time (see
    :func:`_routing_chains`), and an unstaffed step on the second chain strands
    the employees enrolled on it just as surely as one on the first.

    The checks are deliberately about the team's *own* configuration — the
    chains, their sections, their roles, and whether somebody can act at each
    step today. Per-applicant resolution (an applicant who is themselves the
    only approver of a step, say) cannot be known without an application and is
    still refused at submission by invariant 12.7.
    """
    issues: list[TeamIssue] = []
    chains = _routing_chains(team)

    if not chains:
        issues.append(
            TeamIssue(
                "workflow_missing",
                "workflow",
                f"The {team.name} team has no approval workflow. Describe the "
                "approval steps this team routes through, or place its employees "
                "on one of the chains it owns.",
            )
        )
        return TeamReadiness(team=team, issues=tuple(issues))

    for workflow in chains:
        issues.extend(_chain_issues(team, workflow))

    if (
        team.effective_from is not None
        and team.effective_to is not None
        and team.effective_to < team.effective_from
    ):
        issues.append(
            TeamIssue(
                "window_ordered",
                "effective_to",
                f"The end date ({team.effective_to.isoformat()}) is before the "
                f"start date ({team.effective_from.isoformat()}).",
            )
        )

    if team.effective_to is not None and team.effective_to < timezone.localdate():
        issues.append(
            TeamIssue(
                "window_ended",
                "effective_to",
                f"This team's last routing date was "
                f"{team.effective_to.isoformat()}, which has passed. Move the end "
                "date into the future, or leave it blank, to activate the team.",
            )
        )

    return TeamReadiness(team=team, issues=tuple(issues))


def _routing_chains(team: Team) -> list[Workflow]:
    """Every chain the team routes, its default chain first.

    A team routes one or more chains at the same time: its default chain
    (:attr:`Team.workflow` — where somebody nobody enrolled routes, and where a
    wide approver routes when their holding staffs several) and every chain one
    of its people is enrolled on (:class:`~chains.models.WorkflowMember`).
    Readiness that stopped at the default would report a team as ready while a
    second chain it routes has lost its approver, which is exactly the failure
    the check exists to catch.

    A chain nobody is enrolled on and that is not the default routes nothing,
    so it is left out: a replacement chain being built beside the live ones is
    allowed to be incomplete, and reporting it would make every team with a
    draft chain look broken.
    """
    chains: list[Workflow] = []
    default = team.workflow
    if default is not None:
        chains.append(default)
    enrolled_ids = set(
        WorkflowMember.objects.filter(team=team)
        .values_list("workflow_id", flat=True)
        .distinct()
    )
    if default is not None:
        enrolled_ids.discard(default.pk)
    chains.extend(
        Workflow.objects.filter(team=team, pk__in=enrolled_ids).order_by("name")
    )
    return chains


def _chain_issues(team: Team, workflow: Workflow) -> list[TeamIssue]:
    """Every reason one of the team's chains cannot route, or an empty list.

    The chain's own questions: is it switched on, is it in force today, does it
    have steps, and can somebody act at each of them. A step that resolves to
    nobody is reported rather than raised, so one pass names every problem
    across every chain the team routes.
    """
    issues: list[TeamIssue] = []
    today = timezone.localdate()

    if not workflow.is_active:
        issues.append(
            TeamIssue(
                "workflow_inactive",
                "workflow",
                f"Workflow '{workflow.name}' is inactive. Reactivate it, or point "
                f"the {team.name} team at an active workflow.",
            )
        )

    if workflow.effective_from is not None and workflow.effective_from > today:
        issues.append(
            TeamIssue(
                "workflow_scheduled",
                "workflow",
                f"Workflow '{workflow.name}' does not start until "
                f"{workflow.effective_from.isoformat()}. Move its start date "
                f"earlier, or wait until then to activate the {team.name} team.",
            )
        )

    if workflow.effective_to is not None and workflow.effective_to < today:
        issues.append(
            TeamIssue(
                "workflow_ended",
                "workflow",
                f"Workflow '{workflow.name}' stopped routing on "
                f"{workflow.effective_to.isoformat()}. Extend its end date, or "
                "move the employees enrolled on it to a chain that is still in "
                "force.",
            )
        )

    sections = list(
        workflow.sections.filter(is_active=True)
        .order_by("order")
        .select_related("approver_role")
    )
    if not sections:
        issues.append(
            TeamIssue(
                "no_sections",
                "sections",
                f"Workflow '{workflow.name}' has no active approval sections. Add "
                "at least one step before activating the team.",
            )
        )

    for section in sections:
        role = section.approver_role
        if not role.is_active:
            issues.append(
                TeamIssue(
                    "inactive_role",
                    "sections",
                    f'The "{section.name}" step of workflow "{workflow.name}" '
                    f'needs the "{role.label}" role, which is deactivated. '
                    "Reactivate it in Roles, or replace the step.",
                    section=section.order,
                    approver_role=role.code,
                )
            )
            continue
        # A step whose approver has since been deactivated resolves to nobody,
        # which is the same failure as no approver at all: a step HR believes is
        # staffed with somebody who cannot log in. The resolver *raises* for an
        # unstaffable step rather than returning an empty set, so the reason is
        # captured and the whole configuration is still reported.
        try:
            approvers = resolve_section_approvers(section)
        except WorkflowConfigError:
            approvers = ()
        if not approvers:
            if role.is_institution_wide and team.category != Team.Category.ADMINISTRATION:
                hint = (
                    "An institution-wide role may only serve an administration "
                    "team — appoint one of this team's members, or give the role "
                    "a team-wide or campus-wide holder."
                )
            elif team.campus_id is not None:
                hint = (
                    "Appoint somebody from the team, or give the role a "
                    "team-wide or campus-wide holder."
                )
            else:
                hint = (
                    "Appoint somebody from the team, or give the role a "
                    "team-wide holder."
                )
            issues.append(
                TeamIssue(
                    "no_approver",
                    "sections",
                    f'Nobody can act on the "{section.name}" step '
                    f'({role.label}) of workflow "{workflow.name}". {hint}',
                    section=section.order,
                    approver_role=role.code,
                )
            )
        else:
            # An approver appointed before they joined the team, or whose own
            # employee record moved since, still routes — the write-time check only
            # ran when the appointment was made. Report it rather than let a team be
            # activated whose approver is outside it. A wide holding is the
            # deliberate exception: not being on the team is the whole point of
            # one.
            wide_ids = wide_holder_ids(team, role)
            for approver_id in approvers:
                if approver_id in wide_ids:
                    continue
                profile = getattr(
                    User.objects.filter(pk=approver_id).first(), "employee_profile", None
                )
                if profile is not None and profile.team_id != team.pk:
                    issues.append(
                        TeamIssue(
                            "approver_outside_team",
                            "sections",
                            f'The approver of the "{section.name}" step of '
                            f'workflow "{workflow.name}" is no longer a member '
                            "of this team. Appoint one of the team's members, or "
                            "move the approver's employee record.",
                            section=section.order,
                            approver_role=role.code,
                        )
                    )
                    break

    return issues


def _ensure_team_category(team: Team) -> None:
    """Refuse a category/campus pair that cannot mean anything.

    An academic team sits at a campus — that is what makes campus-wide
    approvers reachable for its stages — and an administration team does not,
    because it is the institution that serves it. Checked on every write rather
    than left to a database constraint, because the sentence HR reads has to
    name the fix: create or pick a campus, or switch the category.

    The model's ``clean`` says the same thing; this is the API's copy of it so
    the refusal arrives as a field error instead of a 500.
    """
    try:
        team.full_clean(exclude=["name", "code", "status", "workflow"])
    except ValidationError as exc:
        message_dict = getattr(exc, "message_dict", None)
        if message_dict:
            field, messages = next(iter(message_dict.items()))
            message = messages[0]
        else:
            field, message = "campus", "; ".join(
                str(item) for item in exc.messages
            )
        if field == "__all__":
            # A model-level constraint (the effective-date window) is about the
            # team as a whole, and no form field owns it.
            field = "detail"
        raise TeamActionError(field, message)


def create_team(
    *,
    actor,
    data: dict,
    workflow_config: dict | None = None,
    manager: dict | None = None,
) -> Team:
    """Create a team together with the approval chain it routes through.

    ``data`` holds the team's own editable fields. ``workflow_config`` is
    ``{"name", "sections": [{"name", "approver_role", "approver"}]}`` — the
    chain, its ordered sections, and the one person who may act at each step, all
    created as part of the same transaction as the team.

    ``workflow_config`` is optional, and a team created without one is **in
    force but chainless**. That is the two-page configuration HR performs: the
    team's identity first, its approval steps second. Until it owns a chain it
    routes nothing — there is simply nothing to route through — while still
    being a real, inspectable object that :func:`validate_team` can report on.

    When a chain *is* supplied it is created in the same transaction, so a team
    and its chain are never two objects to keep in step. Everything lands
    together or not at all: a half-built team with a chain but no steps is exactly
    the object that used to look configured and then fail at submission.

    ``manager`` is ``{"role": <ApproverRole>, "user": <User>}``, the second page
    of HR's create flow. When given, that team-scoped role is appointed to the
    person as a team-wide holding and flagged the team's manager, in the same
    transaction as the team, through :func:`create_team_role_assignment`.
    Naming the role *and* the person is the whole instruction: the holding is
    what lets the manager act, so "assign the manager" is not a separate object
    to keep in step.

    A team starts **active**: creating it is the act of putting it in force, and
    HR does not confirm that afterwards — so there is no draft state and no
    activation step. It does not route until it owns a chain.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        data = dict(data)
        data.setdefault("code", _unique_team_code(data.get("name", "")))
        # Creating a team *is* putting it in force, whatever the caller sent:
        # routing is a separate, validated decision that begins once the team
        # owns a chain.
        data["status"] = Team.Status.ACTIVE

        # The team is written first so its chain's steps can be checked against
        # the team — an approver is only eligible relative to the team they are
        # appointed for, and the membership is on the employee record. The whole
        # thing is one transaction, so a bad section list still leaves nothing
        # behind.
        team = Team(**data)
        _ensure_team_category(team)
        team.save()

        if workflow_config is not None:
            config = dict(workflow_config)
            sections_payload = [
                dict(section, approver=section.get("approver"))
                for section in config.get("sections") or []
            ]
            workflow_name = _unique_workflow_name(
                config.get("name") or f"{data.get('name', '').strip()} workflow"
            )
            workflow = Workflow.objects.create(
                name=workflow_name,
                team=team,
                # Dated like any other chain written against a term, so a team
                # created with its steps is not the one configuration whose
                # window is left open-ended.
                effective_from=timezone.localdate(),
                effective_to=academic_calendar_end(),
            )
            team.workflow = workflow
            team.save(update_fields=["workflow", "updated_at"])

            sections = replace_workflow_sections(workflow, sections_payload)
            _attach_section_approvers(
                team=team,
                workflow=workflow,
                sections=sections,
                config=sections_payload,
                actor=actor,
                place_on_team=True,
            )

        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail={"before": None, "after": _team_snapshot(team)},
        )
        if team.workflow_id is not None:
            _shared.record_audit(
                actor=actor,
                action=AuditEntry.Action.CREATED,
                target_type=AuditEntry.TargetType.WORKFLOW,
                target_id=team.workflow_id,
                target_summary=team.workflow.name,
                detail={
                    "before": None,
                    "after": {
                        "name": team.workflow.name,
                        "created_with_team": team.name,
                        "workflow": _workflow_snapshot(team.workflow),
                    },
                },
                reason=f"Created with the {team.name} team.",
            )
        if manager is not None:
            create_team_role_assignment(
                team=team,
                role=manager["role"],
                user=manager["user"],
                actor=actor,
                is_team_manager=True,
            )
    return team

def _appoint_institution_wide_holder(*, section: Section, actor=None) -> None:
    """Appoint the role's holder when a stage selects an institution-wide role.

    A step whose role is institution-wide is not a team's to staff, so the
    team-scoped picker cannot offer the holder and HR would otherwise have to
    leave the step empty. Selecting the role *is* the appointment, so the role's
    active holder is written to the step here.

    Only an unambiguous holding is applied: exactly one active holder. A role
    with none, or with several, is left unstaffed because picking one of many
    would silently decide an ambiguity only HR can resolve — the same rule
    :func:`~workflows.providers.resolve_section_approvers` applies at submission.
    Inspection and validation therefore keep reporting the real problem instead
    of the auto-appointment hiding it.

    An academic team is left unstaffed too, and for a different reason: an
    institution-wide approver may not serve it at all, so appointing one would
    write a configuration the requirement forbids. :func:`validate_team` then
    reports the step with a message that says which way to go.
    """
    role = section.approver_role
    if not role.is_institution_wide:
        return
    team = section.workflow.team if section.workflow_id else None
    if team is not None and team.category != Team.Category.ADMINISTRATION:
        return
    holders = list(
        RoleAssignment.objects.filter(role=role, user__is_active=True)
        .order_by("user_id")
        .select_related("user")
    )
    if len(holders) != 1:
        return
    holder = holders[0].user
    if (
        section.approver_id == holder.pk
        and SectionMember.objects.filter(section=section, user=holder).exists()
    ):
        # Already the configured approver; re-sending the same chain is not a new
        # appointment and must not open a second period for the same person.
        return
    add_section_member(section=section, user=holder, actor=actor)


def _place_new_team_member(*, team: Team, section: Section, user: User) -> None:
    """Put ``user`` on a team being created, so their appointment can be judged.

    A team is its members' organisational unit and a newly created team has no
    roster, so naming somebody one of its approvers is what places them on it.
    This only ever runs while the team is being created in the same transaction.

    Someone already on a *different* team is refused rather than moved. Silently
    moving them would leave the team they came from with approvers who can no
    longer be eligible, and doing that as a side effect of creating some other
    team is not a change HR should get by accident — it is a deliberate edit to
    their employee record, and the message says so. A wide holder is the
    exception: their post already approves for the team from outside it.
    """
    role = section.approver_role
    if role.is_institution_wide:
        # An institution-wide holder approves from outside any team, so there is
        # no membership to establish.
        return
    if holds_role_wide_for_team(team=team, role=role, user=user):
        # A campus-wide holder staffs the new team from their campus without
        # becoming one of its members; placing them on it would re-route their
        # own leave and take them off the team that actually holds them.
        return

    profile = getattr(user, "employee_profile", None)
    if profile is None:
        # No employee record is a real gap, not a placement problem. Leave it to
        # ensure_team_eligibility to refuse with its own message.
        return
    if profile.team_id == team.pk or profile.team_id is None:
        profile.team = team
        profile.save(update_fields=["team"])
        return

    raise TeamActionError(
        "approver",
        f"{user.get_full_name() or user.username} is on "
        f'"{_team_name(profile)}", so they cannot also be an approver for the '
        f'"{team.name}" team. Move them to "{team.name}" on their employee '
        "record first, or appoint someone already on the team.",
    )


def _attach_section_approvers(
    *,
    team: Team,
    workflow: Workflow,
    sections: list[Section],
    config: list[dict],
    actor=None,
    place_on_team: bool = False,
) -> None:
    """Appoint the requested approver on each newly written section.

    Appointment goes through the same guards as the standalone action
    (:func:`ensure_membership_allowed`) so a chain cannot be created with a
    deactivated account, an approver from outside the team, or a second role for
    somebody who already holds one on it — the rules live in one place, and this
    path cannot grant something the other path would refuse.

    The team is passed in rather than looked up because the chain is written
    *before* the team row exists; the team the approver is checked against is the
    one being created.

    ``place_on_team`` is set only by :func:`create_team`. A team *is* its members'
    organisational unit, and a team being created has no roster yet, so naming
    someone as one of its approvers is what puts them on it — otherwise the one
    request that configures a whole team could never succeed, because every
    approver would be refused for belonging to the very team being built. It is
    deliberately not set when rewriting an existing chain: re-pointing a step must
    never quietly move an employee to another team, which is a separate,
    deliberate change to their employee record.
    """
    # Paired by position, not by name: two steps may legitimately share a label
    # (same role, same "Approval" text twice in a row), and matching on the
    # name alone would hand the second step's approver to the first one.
    by_order = {section.order: section for section in sections}
    for position, payload in enumerate(config):
        section = by_order.get(position + 1)
        if section is None:
            continue

        user_pk = payload.get("approver")
        if user_pk in (None, ""):
            # An unstaffed step is allowed at draft time on purpose: HR builds the
            # chain and names the people afterwards, and activation is the gate
            # that refuses a team which is not fully staffed. Refusing it here
            # would force every step to be staffed before the team could even be
            # saved, which is the opposite of what a two-page configuration needs.
            #
            # An institution-wide role is the exception. Its holders approve from
            # outside any one team, so the team-scoped picker cannot offer them
            # and HR has no way to staff the step by hand. Selecting the role
            # is the whole instruction, so the role's single active holder is
            # appointed here. Ambiguity (no holder, or several) is left unstaffed
            # and reported by :func:`validate_team` and submission, exactly as an
            # unstaffed step has always been.
            _appoint_institution_wide_holder(section=section, actor=actor)
            continue
        if isinstance(user_pk, (list, tuple)):
            raise TeamActionError(
                "approver",
                'The "approver" step field takes one person. A step has exactly '
                "one approver — pick the single employee responsible for it.",
            )
        user = User.objects.filter(pk=user_pk, is_active=True).first()
        if user is None:
            raise TeamActionError(
                "approver",
                f"Approver {user_pk} is missing or is not an active user. Pick "
                "an active employee, or activate their account first.",
            )
        if place_on_team:
            _place_new_team_member(team=team, section=section, user=user)
        ensure_membership_allowed(section, user)
        if (
            section.approver_id == user.pk
            and SectionMember.objects.filter(section=section, user=user).exists()
        ):
            # Saving a chain that did not change is not an appointment. Without
            # this, a reorder or a chain rename would close the existing period
            # and open a new one for the same person — history full of handovers
            # nobody made.
            continue
        add_section_member(section=section, user=user, actor=actor)


def update_team(
    *,
    team: Team,
    actor,
    data: dict,
    workflow_config: dict | None = None,
    manager: dict | None = None,
) -> Team:
    """Update a team's editable fields, its steps, and its designated manager.

    ``status`` is not editable here. Teams start in force when HR creates them,
    and the one move left — retirement — goes through :func:`deactivate_team`,
    so it is audited as the distinct event it is rather than being a PATCH that
    quietly took a team out of service.

    ``workflow`` is not editable here: routing a team through one of its chains
    is a decision of its own and goes through :func:`route_team`, so editing a
    team's name can never quietly re-route it.

    ``workflow_config`` replaces the chain's *steps*, not the chain itself: a
    team's chain belongs to it, so the only edit available is the same edit the
    form used to create it. Sections are identified by their (role, name) pair,
    so reordering keeps each step's roster while a role or name change rebuilds
    that step empty. Removing a step an in-flight application is waiting on is
    refused by the ``PROTECT`` on ``ApplicationStage.section_ref``, so an edit
    here cannot rewrite the past.

    ``manager`` is the same ``{"role", "user"}`` instruction as on
    :func:`create_team`: the role is appointed to the person as a team-wide
    holding and designated the team's manager. Passing it re-designates the
    manager without touching anything else.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        before = _team_snapshot(team)
        for field, value in data.items():
            if field in ("status", "workflow"):
                continue
            setattr(team, field, value)
        _ensure_team_category(team)
        team.save()
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=_shared.changed_fields(before, _team_snapshot(team)),
        )

        if workflow_config is not None:
            _replace_team_chain(
                team=team,
                actor=actor,
                config=workflow_config,
            )

        if manager is not None:
            create_team_role_assignment(
                team=team,
                role=manager["role"],
                user=manager["user"],
                actor=actor,
                is_team_manager=True,
            )
    return team

def route_team(*, team: Team, actor, workflow: Workflow) -> Team:
    """Make one of the team's chains its default chain.

    A team routes every chain its people are enrolled on, so this is not a
    switch between one live chain and a standby one: it changes where the
    people nobody has enrolled route, and where a wide approver routes when
    they staff several of the team's chains. It is an action rather than a
    field edit because it changes routing for a whole group of employees. The
    workflow named must be one the team already owns
    (:attr:`Workflow.team`), so "make this the default" can never become
    "adopt somebody else's chain" — which would strand every application
    inside the old one at a step nobody staffs.

    The team's manager owns this day-to-day decision, but HR keeps the same
    reach so an installation that has not yet designated a manager can still
    configure its own teams.
    """
    _require_can_manage_team(actor, team, TeamActionError)
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if workflow is None or workflow.team_id != team.pk:
            raise TeamActionError(
                "workflow",
                "A team can only route through a workflow it owns. Create the "
                "workflow under this team first, then point the team at it.",
            )
        if team.workflow_id == workflow.pk:
            return team
        before = _team_snapshot(team)
        team.workflow = workflow
        team.save(update_fields=["workflow", "updated_at"])
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=_shared.changed_fields(before, _team_snapshot(team)),
            reason=f'Routed through "{workflow.name}".',
        )
    return team

def academic_calendar_end() -> date | None:
    """The last day of the academic calendar a chain is written against.

    The configured academic year — the active
    :class:`leave.models.FinancialYear` — is what "the end of the academic
    calendar" means here: a chain is a statement about a term, so a new one
    runs to the end of the current year rather than open-ended. Nothing
    configured means no boundary at all (``None``), which is what an
    installation that has not set up its year should get rather than a crash
    in a create.
    """
    year = active_financial_year()
    return year.end_date if year is not None else None


def create_workflow(*, team: Team, actor, data: dict) -> Workflow:
    """Build a workflow the team owns, with its stages, in one transaction.

    A team may own several workflows — one per part of its staff, and a
    replacement HR is building alongside them — so a workflow is created *for*
    a team and ownership is written at creation. Ownership is not routing: each
    person follows the chain they are enrolled on (:class:`WorkflowMember`), and
    :attr:`Team.workflow` only decides where somebody nobody has enrolled routes
    and where a wide approver routes when their holding staffs several. It is
    therefore only moved here when the team has no chain at all, because
    silently re-pointing the default of a team that already routes is the one
    change this must never make.

    ``sections`` is the same stage list the team form sends, so stage
    configuration is one implementation whether HR is editing the chain they
    just created or the one a team has used for a year.
    """
    _require_can_manage_team(actor, team, WorkflowActionError)
    with transaction.atomic():
        payload = dict(data)
        sections_payload = payload.pop("sections", None)
        members_payload = payload.pop("members", None)
        # A chain is named for what it approves, not for the team it hangs off:
        # a team has several chains over a year, and "<team name> workflow"
        # cannot be told apart from the team itself or from the replacement
        # beside it. The name is the caller's to give.
        raw_name = str(payload.get("name") or "").strip()
        if not raw_name:
            raise WorkflowActionError(
                "name",
                "Every workflow needs a name of its own. Name it for what it "
                "approves — a chain named after its team cannot be told apart "
                "from the team, or from the replacement chain beside it.",
            )
        workflow = Workflow(
            name=_unique_workflow_name(raw_name),
            team=team,
            # In force from today unless the caller says otherwise, and running
            # to the end of the academic calendar: a chain is written against
            # a term, so it does not outlive one by default.
            effective_from=payload.get("effective_from") or timezone.localdate(),
            effective_to=(
                payload.get("effective_to")
                if payload.get("effective_to") is not None
                else academic_calendar_end()
            ),
            is_active=payload.get("is_active", True),
        )
        workflow.save()

        if sections_payload:
            sections = replace_workflow_sections(
                workflow, [dict(section) for section in sections_payload]
            )
            try:
                _attach_section_approvers(
                    team=team,
                    workflow=workflow,
                    sections=sections,
                    config=[dict(section) for section in sections_payload],
                    actor=actor,
                )
            except TeamActionError as exc:
                # The appointment guard refuses somebody the step cannot hold
                # — most often a person already staffing another of the team's
                # chains, which is exactly what building a second chain runs
                # into. This write path reports that as the field error it is
                # (and rolls the new chain back with the transaction) rather
                # than letting a configuration refusal escape as a server
                # fault.
                raise WorkflowActionError(exc.field, exc.message) from exc

        if team.workflow_id is None:
            team.workflow = workflow
            team.save(update_fields=["workflow", "updated_at"])

        if members_payload is not None:
            sync_workflow_members(
                workflow=workflow, user_ids=members_payload, actor=actor
            )

        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=workflow.name,
            detail={"before": None, "after": _workflow_snapshot(workflow)},
            reason=f"Created for the {team.name} team.",
        )
    return workflow


def update_workflow(*, workflow: Workflow, actor, data: dict) -> Workflow:
    """Edit a workflow's own fields and, optionally, replace its stages.

    Editing stages goes through :func:`replace_workflow_sections`, the same
    function the team form uses, so section identity, ordering, and the
    ``PROTECT`` guard on a step a live application points at are one
    implementation rather than two that can drift.

    A workflow that owns no team cannot be edited here: stage rules are scoped
    to a team (an approver must be a member of it), so there is nothing to check
    an edit against.
    """
    with transaction.atomic():
        locked = Workflow.objects.select_for_update().get(pk=workflow.pk)
        team = locked.team
        if team is None:
            raise WorkflowActionError(
                "team",
                f'"{locked.name}" is not attached to a team, so its stages '
                "cannot be checked against one. Attach it to a team first.",
            )
        before = _workflow_snapshot(locked)

        for field, value in data.items():
            if field in ("sections", "name", "team", "members"):
                continue
            setattr(locked, field, value)
        if data.get("name") and str(data["name"]).strip() != locked.name:
            locked.name = _unique_workflow_name(
                str(data["name"]).strip(), exclude_pk=locked.pk
            )
        locked.save()

        if "members" in data:
            sync_workflow_members(
                workflow=locked, user_ids=data.get("members"), actor=actor
            )

        if data.get("sections") is not None:
            sections_payload = [dict(section) for section in data["sections"]]
            try:
                sections = replace_workflow_sections(locked, sections_payload)
            except StageSequenceError as exc:
                raise WorkflowActionError(exc.field, exc.message)
            try:
                _attach_section_approvers(
                    team=team,
                    workflow=locked,
                    sections=sections,
                    config=sections_payload,
                    actor=actor,
                )
            except TeamActionError as exc:
                # Same translation as :func:`create_workflow`: a refused
                # appointment is a field error on this request, never a 500.
                raise WorkflowActionError(exc.field, exc.message) from exc

        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=locked.pk,
            target_summary=locked.name,
            detail=_shared.changed_fields(before, _workflow_snapshot(locked))
            | {"team": team.name},
            reason=f"Approval steps changed on the {team.name} team.",
        )
    return locked

def _replace_team_chain(*, team: Team, actor, config: dict) -> None:
    """Write the steps of the chain this team owns.

    A team created without one — page 1 of the team form, saved before its steps
    were known — gets its chain created here, so "save the team again with the
    steps" is the same action whether or not the team already had a chain. A team
    that already has one has it rewritten in place, through
    :func:`replace_workflow_sections`, so section identity, ordering, and the
    ``PROTECT`` guard on a step a live application points at are one
    implementation rather than two that can drift.
    """
    config = dict(config)
    sections_payload = [
        dict(section, approver=section.get("approver"))
        for section in config.get("sections") or []
    ]

    workflow = team.workflow
    created = False
    if workflow is None:
        workflow = Workflow.objects.create(
            name=_unique_workflow_name(
                str(config.get("name") or f"{team.name} workflow").strip()
            ),
            team=team,
            # Dated the same way :func:`create_workflow` dates a chain: in force
            # from today and running to the end of the academic calendar, since
            # a chain written inline by the team form is the same statement about
            # a term as one written on its own screen.
            effective_from=config.get("effective_from") or timezone.localdate(),
            effective_to=(
                config.get("effective_to")
                if config.get("effective_to") is not None
                else academic_calendar_end()
            ),
        )
        team.workflow = workflow
        team.save(update_fields=["workflow"])
        created = True
    elif workflow.team_id != team.pk:
        workflow.team = team
        workflow.save(update_fields=["team"])

    before = {} if created else _workflow_snapshot(workflow)
    try:
        sections = replace_workflow_sections(workflow, sections_payload)
    except StageSequenceError as exc:
        raise TeamActionError(exc.field, exc.message)
    if config.get("name") and not created:
        workflow.name = _unique_workflow_name(
            str(config["name"]).strip(), exclude_pk=workflow.pk
        )
        workflow.save(update_fields=["name"])
    _attach_section_approvers(
        team=team,
        workflow=workflow,
        sections=sections,
        config=sections_payload,
        actor=actor,
    )

    _shared.record_audit(
        actor=actor,
        action=AuditEntry.Action.CREATED if created else AuditEntry.Action.UPDATED,
        target_type=AuditEntry.TargetType.WORKFLOW,
        target_id=workflow.pk,
        target_summary=workflow.name,
        detail=_shared.changed_fields(
            before, _workflow_snapshot(workflow)
        )
        | {"team": team.name},
        reason=(
            f"Approval chain created with the {team.name} team."
            if created
            else f"Approval steps changed on the {team.name} team."
        ),
    )


def deactivate_team(*, team: Team, actor) -> Team:
    """Retire a team from routing, keeping its configuration and its history.

    Retiring rather than deleting is the whole reason a team is a
    ``status`` rather than a boolean that HR ticks: an application already
    inside this team's chain still has to be decided, and the stages that prove
    who was entitled to decide it are the team's configuration. The team stops
    routing *new* applications the moment this returns, and everything that
    pointed at it keeps resolving.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        locked = Team.objects.select_for_update().get(pk=team.pk)
        if locked.status == Team.Status.INACTIVE:
            return locked
        if locked.status == Team.Status.DRAFT:
            raise TeamActionError(
                "status",
                f'The {locked.name} team is still a draft, so there is nothing to '
                "retire. Delete it instead.",
            )
        locked.status = Team.Status.INACTIVE
        locked.save(update_fields=["status", "updated_at"])
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=locked.pk,
            target_summary=locked.name,
            detail=_shared.changed_fields(
                {"status": Team.Status.ACTIVE}, {"status": Team.Status.INACTIVE}
            ),
            reason=f"{locked.name} retired from routing.",
        )
    return locked

def _team_snapshot(team: Team) -> dict:
    return {
        "name": team.name,
        "code": team.code,
        "description": team.description,
        # Both the id and the name: the id is what the row points at and the name
        # is what an audit reader can read without a second lookup. A model
        # instance would not survive being written to the audit's JSON detail.
        "campus_id": team.campus_id,
        "campus": team.campus.name if team.campus_id else "",
        "workflow_id": team.workflow_id,
        "status": team.status,
        "effective_from": team.effective_from,
        "effective_to": team.effective_to,
    }
