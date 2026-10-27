"""Workflow and team membership: who is appointed, and to what.

Two related rosters live here. A *section member* is the one person appointed to
a step (:class:`~workflows.models.SectionMember`), and a *workflow member* is a
person in a chain's normal-member eligibility pool
(:class:`~workflows.models.WorkflowMember`). Both obey the same spine of rules —
one employee holds one role per team, sits on one stage per workflow, and serves
one of a team's chains at a time — so those guards are defined once, here, and
every write path routes through them.
"""

from datetime import date

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from campuses.models import CampusRoleAssignment
from roles.models import ApproverRole
from roles.services import (
    WorkflowMemberError,
    _employee_profile_for,
    _member_display_name,
    is_team_manager,
    wide_approver_ids_for_team,
)
from teams.models import Team, TeamRoleAssignment
from users.models import EmployeeProfile, User
from chains.models import Section, SectionMember, Workflow, WorkflowMember
from chains.services import _shared
from chains.services._shared import TeamActionError


def team_for_section(section: Section) -> Team | None:
    """The team this section is staffed from, if any.

    A section belongs to a workflow and a workflow is owned by at most one team
    (:attr:`Workflow.team`), so this is one row at most. It is the bridge that
    turns "the approver must be in the team" into a check the membership path
    can perform without the caller passing the team in separately, and it is
    also what every wide holding — team, campus, institution — is scoped by.

    A chain can genuinely have no team: during creation, before the team row is
    attached, or a workflow imported outside any team. That is a real answer to
    this lookup, not an error to raise out of it.
    """
    if section.workflow_id is None:
        return None
    return section.workflow.team


def holds_role_wide_for_team(
    *, team: Team | None, role: ApproverRole, user: User
) -> bool:
    """Whether ``user`` staffs ``role`` for ``team`` through a wide holding.

    The narrowly-scoped siblings of the institution-wide holding: the holder of
    the role on this team, or the holder of the role at the team's campus. A
    wide holder may approve for a team they are not a member of — that is the
    point of the holding — so this is what exempts them from the membership rule
    when a chain names them at a step. An institution-wide holder is exempt
    separately, because such a role may only serve an administration team and is
    refused elsewhere.
    """
    if team is None:
        return False
    if TeamRoleAssignment.objects.filter(
        team=team, role=role, user=user, user__is_active=True
    ).exists():
        return True
    if team.campus_id is None or team.category != Team.Category.ACADEMIC:
        return False
    return CampusRoleAssignment.objects.filter(
        campus_id=team.campus_id, role=role, user=user, user__is_active=True
    ).exists()


def holds_team_wide_role(*, team: Team | None, user: User) -> bool:
    """Whether ``user`` holds any approver role team-wide on ``team``.

    Broader than :func:`~roles.services.wide_approver_ids_for_team` in exactly
    one way: it includes the team's **designated manager**. That set leaves the
    manager out because a *membership* would re-route their own leave through
    the chain they joined; a **step appointment** is not a membership and does
    not change where their leave routes, so for staffing steps the manager is a
    team-wide holder like any other.
    """
    if team is None:
        return False
    return TeamRoleAssignment.objects.filter(
        team=team, user=user, user__is_active=True
    ).exists()


def ensure_team_eligibility(section: Section, user: User) -> None:
    """Refuse an approver who is not a member of the owning team.

    Two roles are the deliberate exception, and they are exceptions for
    different reasons:

    * an **institution-wide** role is not a team's to staff — a
      vice-chancellor's office approves from outside any team — so it is
      appointed without the membership rule. It is also an *administration*
      office: an academic team may not use one at all, and that is refused
      here rather than silently resolved at submission.
    * a **team-wide or campus-wide** holder may be named on a step of the role
      they hold. They approve for the team without belonging to it, and the
      chain form writes them onto the step when it locks it, so refusing them
      here would make a locked step unsaveable.

    Every other role is scoped, and the scoping is the rule rather than a
    suggestion: somebody approving for a team they are not a member of would be
    approving on a budget and a procedure they do not hold.

    A team with no members cannot scope an approver, so nothing is eligible for
    it. Treating "empty team" as "anybody may approve" would make the rule
    opt-out rather than opt-in, and HR would reach it by creating the team
    before hiring anybody.
    """
    role = section.approver_role
    team = team_for_section(section)
    if role.is_institution_wide:
        if team is not None and team.category != Team.Category.ADMINISTRATION:
            raise TeamActionError(
                "approver",
                f'"{role.label}" is an institution-wide role, and an '
                "institution-wide approver may only serve an administration "
                f'team. "{team.name}" is an academic team — appoint one of its '
                "members to the step, or give the role a team-wide or "
                "campus-wide holder instead.",
            )
        return

    if team is None:
        raise TeamActionError(
            "approver",
            "This chain is not attached to a team yet, so it has nobody to "
            "appoint. Attach the chain to its team first, then appoint an "
            "approver.",
        )

    if holds_role_wide_for_team(team=team, role=role, user=user):
        # The step names the very person who holds this role across the team or
        # its campus. Their post is the appointment; they need no roster row.
        return

    profile = getattr(user, "employee_profile", None)
    if profile is None:
        raise TeamActionError(
            "approver",
            f"{user.get_full_name() or user.username} has no employee record, so "
            f"there is no team to place them on {team.name} with. Complete their "
            "employee record first.",
        )
    if profile.team_id != team.pk:
        raise TeamActionError(
            "approver",
            f"{user.get_full_name() or user.username} is on "
            f'"{_team_name(profile)}", not on the "{team.name}" team this chain '
            "belongs to. An approver must be a member of the team's own team.",
        )


def ensure_role_consistency(section: Section, user: User) -> None:
    """Refuse an appointment that would give one person two roles on a team.

    The rule being enforced: across every team, an employee holds one approver
    role. The same person may be the approver on several teams, but only ever in
    the same capacity.

    Without it, "Dr Ade is the HOD for ICT but the Bursar for Estate" becomes
    reachable, and the consequence is not confusion in a list but in an audit:
    the same person decides a step under two different roles, each with its own
    history scope, so what they could see depends on which team the application
    arrived through. A role is a statement about capacity, and two capacities at
    once is not something HR can explain afterwards.

    Only live appointments are compared. Closed periods are history and cannot
    conflict with what is being set now.
    """
    team = team_for_section(section)
    team_id = team.pk if team is not None else None
    if team_id is None:
        # Nothing to be consistent with; ``ensure_team_eligibility`` is what
        # refuses this configuration, with a message about the missing team.
        return

    conflicting = (
        Section.objects.filter(
            approver=user,
            is_active=True,
            workflow__team__pk=team_id,
        )
        .exclude(approver_role_id=section.approver_role_id)
        .exclude(pk=section.pk)
        .select_related("approver_role", "workflow__team")
        .distinct()
    )
    conflict = conflicting.first()
    if conflict is None:
        return

    conflict_team = team_for_section(conflict)
    team_name = conflict_team.name if conflict_team is not None else "another team"
    raise TeamActionError(
        "approver",
        f"{user.get_full_name() or user.username} is already appointed as "
        f"{conflict.approver_role.label} on the {team_name} team. One employee "
        f"holds one approver role per team: either use "
        f"{conflict.approver_role.label} here too, or appoint somebody else to "
        "this step.",
    )


def _team_name(profile) -> str:
    """The employee's team name, or a placeholder for a missing one."""
    team = getattr(profile, "team", None)
    return team.name if team is not None else "no team"


def ensure_membership_allowed(section: Section, user: User) -> None:
    """Refuse an appointment the section cannot hold, naming what is wrong.

    Shared by the add-approver action and by writing a chain inline with a team,
    so there is one definition of "this person may be appointed here" and no way
    for the two paths to disagree about it.

    Order matters for which refusal HR reads. The per-workflow check runs before
    the per-team role check because an employee on two stages of one chain breaks
    both, and "John is already on step 1 of this workflow" is the more actionable
    of the two messages.
    """
    if not section.is_active:
        raise TeamActionError(
            "section",
            f'The "{section.name}" section is inactive. Activate it before '
            "appointing an approver.",
        )
    if not user.is_active:
        raise TeamActionError(
            "user",
            f"{user.get_full_name() or user.username} is not an active user. "
            "Activate the account before appointing them to a step.",
        )
    if not section.approver_role.is_active:
        raise TeamActionError(
            "section",
            f'"{section.approver_role.label}" is deactivated. Reactivate it in '
            "Roles before appointing an approver to this section.",
        )
    if section.approver_id == user.pk:
        return
    ensure_team_eligibility(section, user)
    ensure_single_stage_per_workflow(section, user)
    ensure_not_assigned_elsewhere(section, user)
    ensure_role_consistency(section, user)


def ensure_single_stage_per_workflow(section: Section, user: User) -> None:
    """Refuse an approver who already holds another stage of the same workflow.

    Unit 30. Within one workflow an employee appears on exactly one stage, which
    is the third leg of "one employee, one stage, one role per workflow". It also
    is what makes the skip-forward routing unambiguous: "the applicant's stage" is
    a single stage precisely because the employee cannot hold two.

    Scoped to ``section.workflow``, so the same person may be the Supervisor on
    one team's chain and the Bursar on another's — the restriction is per
    workflow, never global.

    The section being written is excluded from the comparison, so re-saving a
    step that already appoints this person is not a conflict with itself; that is
    what lets "John moves from step 1 to step 2" through.

    Mirrored by ``section_workflow_approver_unique`` at the database level. This
    check exists to produce a message naming the person and the other step; the
    constraint exists so nothing can route around the check.
    """
    if section.workflow_id is None:
        return
    other = (
        Section.objects.filter(workflow_id=section.workflow_id, approver=user)
        .exclude(pk=section.pk)
        .select_related("approver_role")
        .order_by("order")
        .first()
    )
    if other is None:
        return
    label = user.get_full_name() or user.username
    raise TeamActionError(
        "approver",
        f"{label} is already assigned to step {other.order} "
        f"({other.approver_role.label}) in this workflow. An employee can only "
        "be assigned to one stage per workflow — appoint somebody else to this "
        "step, or remove the other one.",
    )


def ensure_not_assigned_elsewhere(section: Section, user: User) -> None:
    """Refuse an employee who already sits on another of the team's chains.

    The per-workflow rule (:func:`ensure_single_stage_per_workflow`) stops an
    employee at one stage of *one* chain. This rule goes one further: an
    employee sits on at most **one** of the team's chains at a time, whether
    as a step approver or as a normal workflow member. It is what makes a
    second chain a fresh pool rather than a reshuffle of the first one — the
    people who staff the team's live chain are the people that live chain
    needs, and a replacement chain built from them would staff the same
    people twice.

    The one exception is a **wide approver**: somebody whose holdings (team-
    wide on this team, campus-wide at this team's campus, or institution-wide)
    staff a chain automatically. Their exception is deliberate — a team that
    reaches for its registrar or bursar on the second chain is not moving that
    office off the first one, and :func:`workflow_member_pool` and the
    approver picker keep offering them to every chain.

    The team's **designated manager** is included, because this rule is about
    staffing steps rather than enrolment: a manager joins the roster to route
    their own leave and stays an ordinary member of one chain
    (:func:`_ensure_member_not_assigned_elsewhere`), but their team-wide post
    staffs the steps of every chain just as any other holder's does. Excluding
    them here would leave the step the chain form locks to them unsaveable on
    the team's second chain.

    The section's own workflow is excluded from the comparison, so re-saving
    a step that already appoints this person is not a conflict with itself —
    the same convention as :func:`ensure_single_stage_per_workflow`.
    """
    team = team_for_section(section)
    if team is None:
        return
    if user.pk in wide_approver_ids_for_team(team) or holds_team_wide_role(
        team=team, user=user
    ):
        return

    others = list(
        Workflow.objects.filter(team=team)
        .exclude(pk=section.workflow_id)
        .values_list("pk", flat=True)
    )
    if not others:
        return

    label = user.get_full_name() or user.username
    membership = (
        WorkflowMember.objects.filter(
            team=team, user=user, workflow_id__in=others
        )
        .select_related("workflow")
        .first()
    )
    if membership is not None:
        raise TeamActionError(
            "approver",
            f"{label} is already a normal member of the "
            f'"{membership.workflow.name}" workflow on this team. One employee '
            "serves one of the team's chains at a time: remove them there "
            "before appointing them to a step here, or leave them where they "
            "are.",
        )

    other_section = (
        Section.objects.filter(
            workflow_id__in=list(others),
            approver=user,
            is_active=True,
        )
        .select_related("workflow", "approver_role")
        .order_by("order")
        .first()
    )
    if other_section is not None:
        raise TeamActionError(
            "approver",
            f"{label} already staffs step {other_section.order} "
            f"({other_section.approver_role.label}) of the "
            f'"{other_section.workflow.name}" workflow on this team. One '
            "employee serves one of the team's chains at a time: keep them "
            f"on {other_section.workflow.name}, or remove them from it before "
            "appointing them to a step here.",
        )


def add_section_member(
    *, section: Section, user: User, actor, effective_from: date | None = None
) -> SectionMember:
    """Appoint one person as a section's approver and audit it.

    A section holds exactly one approver, so this both sets
    :attr:`Section.approver` and opens the :class:`SectionMember` period that
    records it. Appointing somebody new closes the outgoing person's period
    first: leaving two open rows would make "who holds this step" answerable two
    ways, and the roster the snapshot is built from would no longer be the
    configuration.

    A handover happens now or it does not happen. ``effective_from`` is accepted
    for symmetry with the rest of the history, but a date in the future is
    refused: :attr:`Section.approver` is what the step routes to, so a
    not-yet-started appointment would either route to somebody nobody has told
    they are an approver yet, or leave the step pointed at the outgoing person
    forever. Both are worse than making the change on the day it happens, and the
    outgoing person's period is closed on the day of the handover, so the record
    of who held the step still answers every date.
    """
    today = timezone.localdate()
    starts = effective_from or today
    if starts > today:
        raise TeamActionError(
            "effective_from",
            "An approver takes over on the day you appoint them. A step routes "
            "to whoever is named as its approver right now, so there is no way "
            f'to schedule one for {starts.isoformat()}. Make the change on the '
            "day it happens instead.",
        )
    with transaction.atomic():
        ensure_membership_allowed(section, user)
        if section.approver_id == user.pk:
            # Re-saving a form that did not change must not fail, and must not
            # open a second period for somebody already holding the step. The
            # existing open period *is* the answer, so it is returned unchanged
            # rather than replaced with a fresh one.
            existing = SectionMember.objects.filter(
                section=section, user=user
            ).first()
            if existing is not None:
                return existing
        outgoing = section.approver if section.approver_id != user.pk else None
        if outgoing is not None:
            # Close the period on the day the incoming one starts, so no date is
            # covered by two holders and no date is covered by none.
            SectionMember.objects.filter(
                section=section, user=outgoing, effective_to__isnull=True
            ).update(effective_to=max(starts, today))
        section.approver = user
        section.save(update_fields=["approver"])
        membership = SectionMember(
            section=section,
            user=user,
            effective_from=starts,
        )
        membership.full_clean()
        membership.save()
        # When an employee is assigned as a workflow approver, they automatically
        # become a team member. A wide holder is the deliberate exception: their
        # post approves *across* teams (or across the teams of a campus), and
        # placing them on this one would re-route their own leave through it and
        # take them off whatever team actually holds them.
        team = team_for_section(section)
        is_wide = section.approver_role.is_institution_wide or (
            holds_role_wide_for_team(team=team, role=section.approver_role, user=user)
        )
        if not is_wide:
            try:
                profile = user.employee_profile
            except Exception:
                profile = None
            if profile is not None and team is not None and profile.team_id != team.pk:
                profile.team = team
                profile.save(update_fields=["team"])
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            # The workflow, not one of its teams: a section belongs to the
            # workflow, several teams may share it, and "the first team that
            # happens to use this workflow" would attribute the change to a team
            # whose config did not change.
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=section.workflow_id,
            target_summary=f"{section.workflow.name} / {section.name}",
            detail=_shared.changed_fields(
                {},
                {
                    "approver_user_id": user.pk,
                    "approver": user.get_full_name() or user.username,
                    "section": section.name,
                    "role": section.approver_role.label,
                    "effective_from": membership.effective_from,
                    "replaced_user_id": outgoing.pk if outgoing else None,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} appointed as "
                f"{section.approver_role.label} for the {section.name} section"
                + (
                    f", replacing {outgoing.get_full_name() or outgoing.username}."
                    if outgoing
                    else "."
                )
            ),
        )
    return membership


def remove_section_member(
    *, membership: SectionMember, actor, effective_to: date | None = None
) -> SectionMember:
    """Take one section's approver out of force, keeping the record of it.

    The row is **closed** (``effective_to`` set) rather than deleted, because it
    is a record of who was entitled to act and when. Deleting it would rewrite
    the past: an application approved last month by a person with no membership
    today would be left with an approver no configuration can explain.

    :attr:`Section.approver` is cleared at the same time. A step whose period has
    closed must not keep pointing at the person it closed, or the configuration
    would claim somebody is appointed after they stopped being appointed.

    ``effective_to`` defaults to today, so the person stops routing from today
    onwards — a period ending today still covers today, so they can act on what
    they were given, and stops from tomorrow. A period that has not started yet
    never took effect, so it is removed outright rather than left as a row that
    says somebody held a step they never held.
    """
    with transaction.atomic():
        locked = SectionMember.objects.select_for_update().get(pk=membership.pk)
        section = locked.section
        user = locked.user
        role = section.approver_role
        today = timezone.localdate()
        if effective_to is not None and effective_to < locked.effective_from:
            raise TeamActionError(
                "effective_to",
                f"The membership starts on {locked.effective_from.isoformat()}, "
                f"which is after {effective_to.isoformat()}. The end date cannot "
                "precede the start date.",
            )
        end = effective_to or today

        # A period that has not begun yet never took effect, so removing it
        # deletes the row. A handover that was called off must not leave a record
        # saying somebody was — or was about to be — on a step.
        never_effective = locked.effective_from > today
        detail = _shared.changed_fields(
            {
                "member_user_id": user.pk,
                "member": user.get_full_name() or user.username,
                "section": section.name,
                "role": role.label,
                "effective_to": None,
            },
            {"effective_to": None if never_effective else end},
        )
        if never_effective:
            locked.delete()
            # A period that never took effect cannot have been the section's
            # answer, so clearing the appointment would only take away somebody
            # who was never holding it. Left in place deliberately.
        else:
            locked.effective_to = end
            locked.save(update_fields=["effective_to"])
        if section.approver_id == user.pk:
            # The step no longer has an approver, and the team must say so rather
            # than route to a person whose period has closed. This is the
            # "unstaffed step" case the readiness check reports and activation
            # refuses — the point at which it becomes visible.
            section.approver = None
            section.save(update_fields=["approver"])
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=section.workflow_id,
            target_summary=f"{section.workflow.name} / {section.name}",
            detail=detail,
            reason=(
                f"{user.get_full_name() or user.username} removed from the "
                f"{section.name} section"
                + (
                    "."
                    if never_effective
                    else f", effective {end.isoformat()}."
                )
            ),
        )
        membership = locked
    return membership

def _team_member_blockers(team: Team, user: User) -> list[str]:
    """Every responsibility that stops somebody leaving ``team``.

    Each answer names the responsibility so HR can go and release it, rather
    than a single "cannot remove" that would leave the roster stuck.
    """
    reasons: list[str] = []
    team_workflows = Workflow.objects.filter(team=team)
    workflow_ids = list(team_workflows.values_list("id", flat=True))

    if workflow_ids:
        section_approverships = Section.objects.filter(
            workflow_id__in=workflow_ids, approver=user, is_active=True
        ).select_related("approver_role")
        for section in section_approverships:
            reasons.append(
                f'appointed to the "{section.name}" step '
                f'({section.approver_role.label}) on workflow '
                f'"{section.workflow.name}".'
            )

        open_memberships = SectionMember.objects.filter(
            section__workflow_id__in=workflow_ids, user=user, effective_to__isnull=True
        ).select_related("section", "section__workflow")
        for membership in open_memberships:
            reasons.append(
                f'still holds an open approver period on the '
                f'"{membership.section.name}" step of '
                f'"{membership.section.workflow.name}".'
            )

        workflow_memberships = WorkflowMember.objects.filter(
            workflow_id__in=workflow_ids, user=user
        ).select_related("workflow")
        for membership in workflow_memberships:
            reasons.append(
                f'a normal member of the "{membership.workflow.name}" '
                f'workflow. Remove them from that workflow first.'
            )

    team_role_holdings = TeamRoleAssignment.objects.filter(team=team, user=user).select_related(
        "role"
    )
    for holding in team_role_holdings:
        reasons.append(
            f'the team-wide "{holding.role.label}" holder for this team. '
            "Replace or remove that holding first."
        )
    return reasons


def remove_team_member(*, team: Team, user: User, actor) -> None:
    """Take an employee off a team, refusing while they still hold a role.

    A roster entry that still staffs a step, holds a team-wide role, or is a
    normal member of one of the team's workflows is not idle data: routing and
    validation read it. Clearing it anyway would leave a configuration that
    looks staffed and cannot act, so each responsibility is named and must be
    released first.

    Only the team's designated manager may call this, for the same reason they
    are the only one who may add: the roster is theirs once HR hands the team
    over.
    """
    if not is_team_manager(actor, team):
        raise WorkflowMemberError(
            "detail",
            "Only this team's designated manager can add or remove its "
            "members. Ask HR to name a manager for the team.",
        )
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record.",
        )
    if profile.team_id != team.pk:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not on the {team.name} team.",
        )
    blockers = _team_member_blockers(team, user)
    if blockers:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} still has responsibilities on "
            f"{team.name}: " + " ".join(blockers),
        )
    with transaction.atomic():
        locked_profile = EmployeeProfile.objects.select_for_update().get(
            pk=profile.pk
        )
        if locked_profile.team_id != team.pk:
            raise WorkflowMemberError(
                "user",
                f"{_member_display_name(user)} is not on the {team.name} team.",
            )
        locked_profile.team = None
        locked_profile.save(update_fields=["team"])
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=locked_profile.user_id,
            target_summary=_member_display_name(locked_profile.user),
            detail=_shared.changed_fields(
                {"team_id": team.pk, "team": team.name},
                {"team_id": None, "team": None},
            ),
            reason=f"Removed from the {team.name} team.",
        )


def _workflow_team_or_error(workflow: Workflow) -> Team:
    if workflow.team_id is None:
        raise WorkflowMemberError(
            "team",
            f'Workflow "{workflow.name}" is not attached to a team, so it has '
            "no eligibility pool. Attach it to a team first.",
        )
    return workflow.team

def assign_workflow_member(
    *,
    workflow: Workflow,
    user: User,
    actor,
    added_by: User | None = None,
) -> WorkflowMember:
    """Add one team member to a workflow's normal-member pool.

    The eligibility rule is one line: the person must already be on the
    workflow's team. That is enforced in the service against the employee's
    own :attr:`EmployeeProfile.team_id` — a cross-table rule the unique
    constraint cannot express alone — and again at the database by
    ``workflow_member_team_user_unique``, so a concurrent write that slips past
    the service check is still refused rather than creating a second pool
    entry.

    One employee serves at most one of the team's chains at a time, as a
    normal member *or* as a step approver, so somebody already placed on
    another of the team's chains is refused here too. A wide approver is the
    deliberate exception (see :func:`ensure_not_assigned_elsewhere`): their
    holdings staff chains automatically, so they may sit on several, and the
    row is marked with :attr:`~workflows.models.WorkflowMember.is_wide_approver`
    so the database's conditional uniqueness lets them through. The team's
    manager is not exempt: they joined the roster to route their own leave and
    serves one chain like any other member.
    """
    team = _workflow_team_or_error(workflow)
    if not user.is_active:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not an active user. Activate the "
            "account before adding them to a workflow.",
        )
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record, so they "
            "cannot be a workflow member. Complete their employee record first.",
        )
    if profile.team_id != team.pk:
        team_name = profile.team.name if profile.team else "no team"
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not on the {team.name} team "
            f'(they are on "{team_name}"). Add them to the team first — a '
            "normal workflow member is always a member of the workflow's team.",
        )

    existing_here = WorkflowMember.objects.filter(workflow=workflow, user=user).first()
    if existing_here is not None:
        return existing_here

    is_wide = user.pk in wide_approver_ids_for_team(team)
    if not is_wide:
        _ensure_member_not_assigned_elsewhere(
            team=team, user=user, workflow=workflow
        )

    with transaction.atomic():
        member = WorkflowMember.objects.create(
            workflow=workflow,
            user=user,
            team=team,
            is_wide_approver=is_wide,
            added_by=added_by or actor,
        )
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=f"{workflow.name} / normal member",
            detail=_shared.changed_fields(
                {},
                {
                    "user_id": user.pk,
                    "user": _member_display_name(user),
                    "team": team.name,
                },
            ),
            reason=(
                f"{_member_display_name(user)} added as a normal member of the "
                f"{workflow.name} workflow."
            ),
        )
    return member


def _ensure_member_not_assigned_elsewhere(
    *, team: Team, user: User, workflow: Workflow
) -> None:
    """Refuse placing ``user`` on ``workflow`` when they already serve another.

    The same one-chain-per-employee rule as :func:`ensure_not_assigned_elsewhere`,
    from the membership side: a person who is already a normal member of
    another of the team's chains, or already staffs a step of one, cannot be
    placed on this one. Called only for non-wide members, so the refusal
    messages can be plain about "one chain per employee".
    """
    label = _member_display_name(user)
    elsewhere_row = (
        WorkflowMember.objects.filter(team=team, user=user)
        .exclude(workflow=workflow)
        .select_related("workflow")
        .first()
    )
    if elsewhere_row is not None:
        raise WorkflowMemberError(
            "user",
            f"{label} is already a normal member of the "
            f'"{elsewhere_row.workflow.name}" workflow on this team. One '
            "employee is a normal member of one workflow per team — remove "
            "them there first, or leave them where they are.",
        )

    other_section = (
        Section.objects.filter(
            workflow__team=team,
            approver=user,
            is_active=True,
        )
        .exclude(workflow=workflow)
        .select_related("workflow", "approver_role")
        .order_by("order")
        .first()
    )
    if other_section is not None:
        raise WorkflowMemberError(
            "user",
            f"{label} already staffs step {other_section.order} "
            f"({other_section.approver_role.label}) of the "
            f'"{other_section.workflow.name}" workflow on this team. One '
            "employee serves one of the team's chains at a time — remove them "
            "from its steps first, or leave them where they are.",
        )


def remove_workflow_member(*, member: WorkflowMember, actor) -> None:
    """Remove one person from a workflow's normal-member pool."""
    with transaction.atomic():
        locked = WorkflowMember.objects.select_for_update().select_related(
            "workflow", "user", "team"
        ).get(pk=member.pk)
        workflow = locked.workflow
        user = locked.user
        locked.delete()
        _shared.record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=f"{workflow.name} / normal member",
            detail=_shared.changed_fields(
                {
                    "user_id": user.pk,
                    "user": _member_display_name(user),
                    "team": locked.team.name if locked.team else None,
                },
                {},
            ),
            reason=(
                f"{_member_display_name(user)} removed as a normal member of "
                f"the {workflow.name} workflow."
            ),
        )

def _pool_person(profile: EmployeeProfile, extra: dict | None = None) -> dict:
    user = profile.user
    payload = {
        "id": user.pk,
        "user": user.pk,
        "full_name": _member_display_name(user),
        "email": user.email,
        "designation": profile.designation,
        "category": profile.category,
        "faculty": profile.faculty,
        "grade": profile.grade,
        "is_active": user.is_active,
    }
    if extra:
        payload.update(extra)
    return payload


def workflow_member_pool(*, team: Team, workflow: Workflow | None = None) -> dict:
    """The eligibility pool for a team's workflow memberships.

    ``available`` is every active team member who is not already serving
    another of the team's chains — as a normal member (:class:`WorkflowMember`)
    or as the single approver staffing a step of one. A **wide approver** is
    the exception and stays available: their holdings staff another chain
    automatically, and a team reuses its registrar or bursar on a second chain
    rather than moving them off the first. The team's manager is not part of
    that exception: once placed on a chain they are an ordinary member of it,
    and disappear from the other chains' pools. When ``workflow`` is given, its
    own members are included in ``available`` (they are already selected) and
    listed separately under ``current`` so a client can render them as checked
    rather than as a second assignment.

    ``assigned_elsewhere`` is people the team has already placed on a
    different chain, with the workflow named so the refusal message and the UI
    can both say where they already sit. Each row also says ``kind``: a
    ``"member"`` is a normal member of that chain, while a ``"step"`` staffs
    one of its steps. Neither is offerable here — a person serves one chain of
    the team at a time — so both can only join this one after being removed
    from the chain they are on.
    """
    team_profiles = list(
        EmployeeProfile.objects.filter(team=team, user__is_active=True)
        .select_related("user", "team")
        .order_by("user__first_name", "user__last_name", "user_id")
    )
    memberships = WorkflowMember.objects.filter(team=team).select_related(
        "workflow", "user"
    )
    by_workflow: dict[int, list[WorkflowMember]] = {}
    for membership in memberships:
        by_workflow.setdefault(membership.workflow_id, []).append(membership)

    current_ids: set[int] = set()
    if workflow is not None:
        current_ids = {m.user_id for m in by_workflow.get(workflow.pk, [])}

    member_elsewhere: dict[int, WorkflowMember] = {}
    for wf_id, rows in by_workflow.items():
        if workflow is not None and wf_id == workflow.pk:
            continue
        for row in rows:
            member_elsewhere[row.user_id] = row

    # Staffing a step of another chain is every bit as "assigned" as being a
    # normal member of one, so step approvers are pooled the same way. Wide
    # approvers are re-added to ``available`` below, whichever source marks
    # them.
    approver_elsewhere: dict[int, tuple[int, str]] = {}
    approver_sections = Section.objects.filter(
        is_active=True, approver__isnull=False, workflow__team=team
    )
    if workflow is not None:
        approver_sections = approver_sections.exclude(workflow=workflow)
    for row in approver_sections.values(
        "approver_id", "workflow__id", "workflow__name"
    ).distinct():
        if row["approver_id"] not in member_elsewhere:
            approver_elsewhere[row["approver_id"]] = (
                row["workflow__id"],
                row["workflow__name"],
            )

    wide_ids = wide_approver_ids_for_team(team)
    elsewhere_ids = (set(member_elsewhere) | set(approver_elsewhere)) - wide_ids
    profiles_by_user = {profile.user_id: profile for profile in team_profiles}

    elsewhere_payload: list[dict] = []
    for user_id in sorted(elsewhere_ids):
        if user_id in member_elsewhere:
            row = member_elsewhere[user_id]
            profile = profiles_by_user.get(user_id)
            if profile is None:
                # A member of another chain who is no longer an active member
                # of the team: not offerable, but still named so the UI can say
                # where they sit.
                user = row.user
                elsewhere_payload.append(
                    {
                        "id": user.pk,
                        "user": user.pk,
                        "full_name": _member_display_name(user),
                        "email": user.email,
                        "workflow_id": row.workflow_id,
                        "workflow_name": row.workflow.name,
                        "kind": "member",
                    }
                )
                continue
            payload = _pool_person(
                profile,
                {
                    "workflow_id": row.workflow_id,
                    "workflow_name": row.workflow.name,
                    "kind": "member",
                },
            )
        else:
            profile = profiles_by_user.get(user_id)
            if profile is None:
                # Someone staffing a step of another chain from off the team:
                # no longer assignable, and not part of this team's pool.
                continue
            wf_id, wf_name = approver_elsewhere[user_id]
            payload = _pool_person(
                profile,
                {
                    "workflow_id": wf_id,
                    "workflow_name": wf_name,
                    "kind": "step",
                },
            )
        elsewhere_payload.append(payload)

    available = [
        _pool_person(profile)
        for profile in team_profiles
        if profile.user_id not in elsewhere_ids
    ]
    current = [
        _pool_person(
            next(p for p in team_profiles if p.user_id == user_id)
        )
        for user_id in sorted(current_ids)
        if any(p.user_id == user_id for p in team_profiles)
    ]
    # Members of the current workflow who are no longer active team members
    # still appear under ``current`` so the edit screen can show and clear them.
    current_user_ids = {row["user"] for row in current}
    for membership in by_workflow.get(workflow.pk if workflow else None, []) or []:
        if membership.user_id in current_user_ids:
            continue
        current.append(
            {
                "id": membership.user_id,
                "user": membership.user_id,
                "full_name": _member_display_name(membership.user),
                "email": membership.user.email,
                "designation": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "designation",
                    "",
                )
                or "",
                "category": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "category",
                    "",
                )
                or "",
                "faculty": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "faculty",
                    "",
                )
                or "",
                "grade": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "grade",
                    "",
                )
                or "",
                "is_active": membership.user.is_active,
            }
        )

    workflow_payload = None
    if workflow is not None:
        workflow_payload = {
            "id": workflow.pk,
            "name": workflow.name,
            "state": workflow.state,
            "is_active": workflow.is_active,
            "is_routing": team.workflow_id == workflow.pk,
        }

    return {
        "team": {"id": team.pk, "name": team.name, "code": team.code},
        "workflow": workflow_payload,
        "available": available,
        "current": current,
        "assigned_elsewhere": sorted(
            elsewhere_payload, key=lambda row: (row["full_name"], row["workflow_name"])
        ),
    }


def sync_workflow_members(
    *, workflow: Workflow, user_ids: list[int] | None, actor
) -> list[WorkflowMember]:
    """Replace a workflow's normal-member list with ``user_ids``.

    Used by the workflow write path so HR can set membership in the same pass
    as the chain itself. ``None`` means "leave membership alone"; an empty list
    means "clear it".

    A person may serve only one of the team's chains at a time. Naming somebody
    who is already a normal member of another chain is **refused** rather than
    moving them: this list says who is on *this* chain, and taking them off the
    other one would silently change a chain this write does not own. The same
    goes for somebody who staffs a step of another chain — free them from that
    chain first, then add them here.

    Every id is validated through :func:`assign_workflow_member`, so a write
    cannot smuggle in somebody from another team and the one-chain rule is
    re-checked inside the transaction. The refusal rolls the whole write back,
    so a member list that mixed free and already-placed people leaves every
    chain exactly as it was.
    """
    if user_ids is None:
        return list(
            WorkflowMember.objects.filter(workflow=workflow).select_related("user")
        )
    team = _workflow_team_or_error(workflow)
    wanted_ids = list(dict.fromkeys(int(pk) for pk in user_ids))
    users = {
        user.pk: user
        for user in User.objects.filter(pk__in=wanted_ids, is_active=True)
    }
    missing = [pk for pk in wanted_ids if pk not in users]
    if missing:
        raise WorkflowMemberError(
            "members",
            f"Workflow member {missing[0]} is missing or is not an active user.",
        )

    with transaction.atomic():
        current = {
            membership.user_id: membership
            for membership in WorkflowMember.objects.filter(workflow=workflow)
        }
        for user_id, membership in list(current.items()):
            if user_id not in wanted_ids:
                remove_workflow_member(member=membership, actor=actor)

        before_ids = set(current)
        members: list[WorkflowMember] = []
        for user_id in wanted_ids:
            user = users[user_id]
            try:
                members.append(
                    assign_workflow_member(
                        workflow=workflow,
                        user=user,
                        actor=actor,
                        added_by=actor,
                    )
                )
            except WorkflowMemberError as exc:
                # The request is writing this chain's member list, so report the
                # refusal against that list rather than against a single-user
                # endpoint the caller did not use.
                raise WorkflowMemberError("members", exc.message) from exc
        after_ids = {membership.user_id for membership in members}
        if before_ids != after_ids:
            _shared.record_audit(
                actor=actor,
                action=AuditEntry.Action.UPDATED,
                target_type=AuditEntry.TargetType.WORKFLOW,
                target_id=workflow.pk,
                target_summary=f"{workflow.name} / normal members",
                detail=_shared.changed_fields(
                    {"user_ids": sorted(before_ids)},
                    {"user_ids": sorted(after_ids), "team": team.name},
                ),
                reason=f"Normal workflow members updated on {workflow.name}.",
            )
        return members


def team_member_summaries(team: Team) -> list[dict]:
    """Roster rows for the team members screen, with their workflow footprint."""
    profiles = (
        EmployeeProfile.objects.filter(team=team)
        .select_related("user", "team")
        .order_by("user__first_name", "user__last_name", "user_id")
    )
    workflow_ids = list(Workflow.objects.filter(team=team).values_list("id", flat=True))
    memberships_by_user: dict[int, list[WorkflowMember]] = {}
    if workflow_ids:
        for membership in WorkflowMember.objects.filter(
            workflow_id__in=workflow_ids
        ).select_related("workflow", "user"):
            memberships_by_user.setdefault(membership.user_id, []).append(membership)

    approver_user_ids = set()
    if workflow_ids:
        approver_user_ids = set(
            Section.objects.filter(
                workflow_id__in=workflow_ids, is_active=True, approver__isnull=False
            ).values_list("approver_id", flat=True)
        )

    role_holdings = {
        holding.user_id: holding.role.code
        for holding in TeamRoleAssignment.objects.filter(team=team).select_related("role")
    }

    rows: list[dict] = []
    for profile in profiles:
        user = profile.user
        memberships = memberships_by_user.get(user.pk, [])
        rows.append(
            {
                "id": user.pk,
                "user": user.pk,
                "full_name": _member_display_name(user),
                "email": user.email,
                "designation": profile.designation,
                "category": profile.category,
                "faculty": profile.faculty,
                "grade": profile.grade,
                "is_active": user.is_active,
                "is_section_approver": user.pk in approver_user_ids,
                "team_role": role_holdings.get(user.pk),
                "workflow_memberships": [
                    {
                        "workflow_id": membership.workflow_id,
                        "workflow_name": membership.workflow.name,
                    }
                    for membership in memberships
                ],
                "workflow_count": len(memberships),
            }
        )
    return rows
