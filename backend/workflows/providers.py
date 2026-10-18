"""Workflow provider contract and real implementation (Unit 16, Unit 21).

The workflow provider resolves the ordered approver chain (stage definitions)
for a submitted leave application. It is the single point of swappability:
:func:`get_workflow_provider` reads ``settings.WORKFLOW_PROVIDER``.

The default is :class:`DatabaseWorkflowProvider`, which resolves the applicant's
**team** to the one workflow that team routes through, and maps its
``Section`` rows into ``StageDefinition`` objects. Each section's approver is
found by :func:`resolve_section_approvers`: the section's appointed approver
unless that person is the applicant, or — when the section has no approver —
the narrowest wide holding that applies, being the team's holder for the role,
then the holder at the team's campus, then, for an administration team, the
role's single institution-wide holder. A section names one person, so a step
always has exactly one person entitled to act on it. The provider is pure data
(no writes): it returns planned stages only. The assignment service
(``workflows.services.assign_workflow``) validates them and materialises them
as ``ApplicationStage`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from users.models import User

from organisation.models import ApproverRole, CampusRoleAssignment, RoleAssignment, Team, TeamRoleAssignment
from workflows.models import SectionMember


class WorkflowConfigError(ValueError):
    """Raised when a workflow definition is malformed or unsatisfiable."""


@dataclass(frozen=True)
class StageDefinition:
    """One planned stage returned by a workflow provider.

    ``approver_user_ids`` is the set of people entitled to act on the stage. A
    section names one approver, so in practice this holds a single id; it stays a
    tuple because the stage is the snapshot of a resolved step, not the
    resolution itself. It is never empty: a section nobody can act for is a
    configuration error and is refused at resolution time rather than routed to a
    fallback (invariant 12.7).

    ``skipped`` marks a stage the applicant's own position made unnecessary
    (Unit 30) -- the stages at and below the one they hold. A skipped stage is
    still materialised, so the approval history can show that it was considered
    and why it was passed over, but it is never pending and never notified.
    ``skip_reason`` is the sentence shown to whoever reads that history.
    """

    order: int
    role: str
    role_label: str
    approver_user_ids: tuple[int, ...] = ()
    role_id: int | None = None
    history_scope: str | None = None
    handles_cancellation: bool = False
    section_id: int | None = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass(frozen=True)
class CancellationStageSpec:
    """One planned cancellation stage (Unit 18, spec 3.2).

    Built from the application's *original* workflow snapshot (the materialised
    stage chain under ``workflow_chain_cycle``), filtered to the stages whose
    snapshotted role handles cancellations, in original order. Snapshot reads
    are provider-agnostic, so a later workflow configuration change never affects
    a cancellation.
    """

    order: int
    role: str
    role_label: str
    approver_user_ids: tuple[int, ...] = ()


class WorkflowProvider(Protocol):
    """The interface every workflow provider must satisfy."""

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]: ...

    def get_cancellation_stages(
        self, application: Any
    ) -> list[CancellationStageSpec]: ...

    def get_workflow_member_user_ids(self, application: Any) -> list[int]: ...


def get_workflow_provider() -> WorkflowProvider:
    """Instantiate the configured workflow provider."""
    return import_string(settings.WORKFLOW_PROVIDER)()


def _employee_team(application: Any):
    """The applicant's team, or ``None`` when they have not been assigned one."""
    profile = getattr(application.employee, "employee_profile", None)
    if profile is None:
        return None
    return profile.team


def _institution_wide_holder_ids(role: ApproverRole) -> list[int]:
    """Active users holding ``role`` institution-wide, lowest id first."""
    return list(
        RoleAssignment.objects.filter(role=role, user__is_active=True)
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )


def _team_wide_holder_ids(team: Team, role: ApproverRole) -> list[int]:
    """Active users holding ``role`` team-wide on ``team``, lowest id first."""
    if team is None:
        return []
    return list(
        TeamRoleAssignment.objects.filter(
            team=team, role=role, user__is_active=True
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )


def _campus_wide_holder_ids(campus, role: ApproverRole) -> list[int]:
    """Active users holding ``role`` campus-wide at ``campus``."""
    if campus is None:
        return []
    return list(
        CampusRoleAssignment.objects.filter(
            campus=campus, role=role, user__is_active=True
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )


def _routing_team(section) -> Team | None:
    """The team that owns the section's workflow, if any.

    :attr:`Workflow.team` is the ownership link; :attr:`Team.workflow` is the
    routing one. A section is always owned, so this answers "which team's
    configuration staffs this step" — which is what every wide holding is
    scoped by.
    """
    workflow = section.workflow_id
    if workflow is None:
        return None
    return section.workflow.team


def _wide_holder_ids(section) -> tuple[str, list[int]]:
    """Who can staff ``section`` without being appointed to it directly.

    Returns ``(source, holder_ids)`` where ``source`` is ``"team"``,
    ``"campus"``, ``"institution"`` or ``"none"`` — the *narrowest* wide
    holding that applies, in the order a step is staffed: the team's own
    holder first, then the applicant's campus, then — for an administration
    team only — the institution.

    Empty holder lists are returned rather than raised: "no holder" and
    "several holders" are two different sentences for HR, and
    :func:`resolve_section_approvers` is the one that writes them.
    """
    role = section.approver_role
    team = _routing_team(section)

    if team is not None:
        holders = _team_wide_holder_ids(team, role)
        if holders:
            return ("team", holders)
        if team.campus_id is not None:
            holders = _campus_wide_holder_ids(team.campus, role)
            if holders:
                return ("campus", holders)

    if not role.is_institution_wide:
        return ("none", [])
    if team is not None and team.category != Team.Category.ADMINISTRATION:
        # An institution-wide approver is an administration office. An academic
        # team routes through its own members and its campus, and saying so is
        # more useful than letting the stage fall through to an office the
        # requirement says it may not use.
        return ("none", [])
    return ("institution", _institution_wide_holder_ids(role))


def resolve_section_approvers(section, applicant_id: int | None = None) -> tuple[int, ...]:
    """The one person entitled to act for ``section``, or raise.

    The single authoritative resolution algorithm:

    1. :attr:`Section.approver`, unless that is the applicant. A section has
       exactly one approver by construction, so this returns a single id or
       nothing. The applicant is excluded at resolution time rather than at
       configuration time, so an approver can never be the approver of their own
       leave no matter which surface asks later (invariant 12.3).

       The applicant holding a stage is decided upstream, not here:
       :func:`DatabaseWorkflowProvider.get_stage_definitions` marks that stage and
       everything below it skipped rather than resolving it at all (Unit 30). The
       refusal below is what catches a caller that asks this function directly,
       which is why it stays rather than becoming a branch nothing can reach.
    2. Only when the section has no approver at all does a **wide holding**
       decide — and the narrowest one wins: the team's holder for the role, then
       the holder at the team's campus, then, for an administration team, the
       institution-wide holder. A wide holding must name exactly one active
       person, because a fallback nobody can see cannot arbitrate a tie.
    3. Otherwise the configuration is incomplete and the submission is refused.

    The fallback exists for a real case, not as a convenience. A team cannot
    appoint a vice-chancellor, so an institution-wide step may reach its office
    without a team staffing it — and the same is true of a registrar's office
    that serves a whole campus. But only when the team has genuinely left the
    step unstaffed. A section that *has* an approver never falls through, so
    HR's explicit configuration always wins over any wide holding.

    Only a **configured, active** approver routes. :attr:`Section.approver` is
    the configuration; the effective-dated record is the roster. A step whose
    approver has been deactivated falls through to the wide holdings for an
    institution-wide role and is refused otherwise, because routing to an
    inactive account would hand an approval to somebody who cannot act.

    Every error names the role, names the section, and says what HR has to do
    about it.
    """
    role = section.approver_role
    approver_id = section.approver_id
    if approver_id is not None:
        active = section.approver.is_active if section.approver_id else False
        if active:
            if applicant_id is not None and approver_id == applicant_id:
                raise WorkflowConfigError(
                    f"The approver of the \"{section.name}\" section is the "
                    "applicant themself, and an approver cannot approve their own "
                    "leave. Appoint somebody else to this step."
                )
            return (approver_id,)
        # A deactivated account is not an approver. For an institution-wide role
        # the office may still have a holder; for a team-scoped role the step is
        # simply unstaffed and HR has to appoint somebody.
        if not role.is_institution_wide:
            raise WorkflowConfigError(
                f'The approver of the "{section.name}" section '
                f"({section.approver.get_full_name() or section.approver.username}) "
                "is no longer an active user. Appoint somebody else to this step."
            )

    source, holders = _wide_holder_ids(section)
    if source in ("team", "campus"):
        if len(holders) == 1:
            holder = holders[0]
            if applicant_id is not None and holder == applicant_id:
                raise WorkflowConfigError(
                    f'The "{section.name}" section routes to the '
                    f"{role.label} role, whose only holder is the applicant "
                    "themself, and an approver cannot approve their own leave."
                )
            return (holder,)
        # A team-wide and a campus-wide holding are one row each by unique
        # constraint, so this cannot be reached today. It is kept because the
        # alternative — silently picking one — is exactly the ambiguity the
        # institution-wide branch refuses below.
        raise WorkflowConfigError(
            f'The "{section.name}" section has no approver, and the '
            f"{role.label} role has multiple holders. Appoint somebody to the "
            "step, or leave a single holder in place."
        )

    if source == "institution":
        if len(holders) == 1:
            holder = holders[0]
            if applicant_id is not None and holder == applicant_id:
                raise WorkflowConfigError(
                    f'The "{section.name}" section routes to the '
                    f"{role.label} role, whose only holder is the applicant "
                    "themself, and an approver cannot approve their own leave."
                )
            return (holder,)
        if not holders:
            raise WorkflowConfigError(
                f'The "{section.name}" section has no approver, and the '
                f"{role.label} role has no active holder. Appoint somebody to "
                "the step, or ask HR to assign one."
            )
        raise WorkflowConfigError(
            f'The "{section.name}" section has no approver, and the '
            f"{role.label} role has multiple active holders. Appoint somebody to "
            "the step, or ask HR to designate exactly one."
        )

    team = _routing_team(section)
    if role.is_institution_wide and team is not None:
        raise WorkflowConfigError(
            f'The "{section.name}" section has no approver, and "{role.label}" '
            "is an institution-wide role, which an academic team may not use. "
            f"Appoint one of the {team.name} team's members to the step, or give "
            "the role a team-wide or campus-wide holder."
        )

    raise WorkflowConfigError(
        f'The "{section.name}" section has no approver. Appoint one of the '
        f"{role.label} from the team, or give the role a team-wide holder."
    )


def section_resolution(section) -> tuple[str, int | None]:
    """Where ``section``'s approver comes from, for configuration screens.

    Returns ``(source, user_id)`` with ``source`` one of:

    ``section``
        A person was appointed to this step by hand — the workflow-specific
        approver, and always the winner because it is the explicit one.
    ``team`` / ``campus`` / ``institution``
        The step is unstaffed and a wide holding resolves it automatically.
    ``unresolved``
        Nothing can staff the step yet.

    Display only: it never raises, so a screen can show an ambiguous
    institution-wide role as "unresolved" while
    :func:`resolve_section_approvers` still refuses it at submission.
    """
    if section.approver_id is not None and section.approver_id and section.approver.is_active:
        role = section.approver_role
        if role.is_institution_wide:
            # Institution-wide is the one wide holding that writes itself onto
            # the section when the role is chosen, so an approver who *is* the
            # role's sole holder was resolved, not picked.
            if _institution_wide_holder_ids(role) == [section.approver_id]:
                return ("institution", section.approver_id)
        return ("section", section.approver_id)
    source, holders = _wide_holder_ids(section)
    if source in ("team", "campus", "institution") and len(holders) == 1:
        return (source, holders[0])
    return ("unresolved", None)


class SnapshotStagesMixin:
    """Cancellation/workflow-membership reads from the materialised stage chain.

    These are provider-agnostic: they read the ``ApplicationStage`` snapshot
    (the chain created at submission and reused across resubmissions), so they
    never consult the live workflow configuration.
    """

    def get_cancellation_stages(
        self, application: Any
    ) -> list[CancellationStageSpec]:
        """The cancellation-handling stages of the application's snapshot.

        Selected on the stage's own snapshotted ``handles_cancellation`` flag
        rather than on a role name, so an application submitted while a role
        handled cancellations keeps that behaviour after HR retires it from the
        role, and one submitted before it gained the flag never picks it up.

        The approvers come from each stage's ``eligible_approvers`` snapshot,
        not from ``assigned_approver``: a section is resolved by whoever acts
        first, and ``assigned_approver`` is null until somebody does.
        """
        from approvals.models import ApplicationStage

        stages = (
            ApplicationStage.objects.filter(
                application=application,
                submission_cycle=_chain_cycle(application),
                handles_cancellation=True,
            )
            .order_by("stage_order")
            .only("stage_order", "role", "role_label")
        )
        return [
            CancellationStageSpec(
                order=stage.stage_order,
                role=stage.role,
                role_label=stage.role_label or stage.role,
                approver_user_ids=stage.eligible_approver_ids(),
            )
            for stage in stages
        ]

    def get_workflow_member_user_ids(self, application: Any) -> list[int]:
        """Every user in the original workflow snapshot (event recipients).

        Reads the ``eligible_approvers`` snapshot rather than
        ``assigned_approver``: a step is still undecided until somebody acts, so
        ``assigned_approver`` is null until then and would leave every approver in
        the chain out of the recipient list.
        """
        from approvals.models import ApplicationStage, ApplicationStageApprover

        return list(
            ApplicationStageApprover.objects.filter(
                stage__application=application,
                stage__submission_cycle=_chain_cycle(application),
            )
            .order_by("user_id")
            .values_list("user_id", flat=True)
            .distinct()
        )


class DatabaseWorkflowProvider(SnapshotStagesMixin):
    """Workflow provider backed by the real HR team and role configuration.

    The applicant's :class:`~workflows.models.Team` names the workflow; the
    workflow's ordered :class:`~workflows.models.Section` rows are its steps; and
    each section's appointed approver is resolved by
    :func:`resolve_section_approvers`, with the applicant removed.
    """

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]:
        team = _employee_team(application)
        if team is None:
            raise WorkflowConfigError(
                "This employee is not in a team. Ask HR to assign them to a team "
                "before they submit a leave application."
            )
        # The team's own status is the gate. A draft team is being configured and
        # an inactive one has been retired; neither routes, and saying so here
        # means the applicant's failure names the team rather than surfacing as
        # some later stage error nobody can act on.

        if team.status == Team.Status.INACTIVE:
            raise WorkflowConfigError(
                f"The {team.name} team is inactive. Ask HR to move the employee "
                "to a team that is still in force."
            )
        if not team.is_effective:
            today = timezone.localdate()
            if team.effective_from is not None and team.effective_from > today:
                raise WorkflowConfigError(
                    f"The {team.name} team does not start until "
                    f"{team.effective_from.isoformat()}. Ask HR to bring its start "
                    "date forward, or to move the employee to an active team."
                )
            raise WorkflowConfigError(
                f"The {team.name} team stopped routing applications on "
                f"{team.effective_to.isoformat()}. Ask HR to move the employee to "
                "a team that is still in force."
            )
        workflow = team.workflow
        if workflow is None:
            raise WorkflowConfigError(
                f"The {team.name} team has no approval workflow. Ask HR to create "
                "one for it, with at least one section."
            )
        if not workflow.is_active:
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' is not in force. Ask HR to point "
                f"the {team.name} team at a workflow that is."
            )
        if (
            workflow.effective_from is not None
            and workflow.effective_from > timezone.localdate()
        ):
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' does not start until "
                f"{workflow.effective_from.isoformat()}. Ask HR to point the team "
                "at a workflow that starts now."
            )

        sections = list(
            workflow.sections.filter(is_active=True)
            .order_by("order")
            .select_related("approver_role", "approver")
            .prefetch_related("members__user")
        )
        if not sections:
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' has no active approval sections."
            )

        applicant_id = getattr(application, "employee_id", None)
        applicant_order = _applicant_section_order(sections, applicant_id)

        definitions: list[StageDefinition] = []
        for section in sections:
            role = section.approver_role
            skip_reason = _skip_reason_for(section, applicant_order)
            definitions.append(
                StageDefinition(
                    order=section.order,
                    role=role.code,
                    role_label=role.label,
                    # A skipped stage resolves nobody on purpose: its whole point
                    # is that the applicant must not be the one who acts there.
                    approver_user_ids=(
                        ()
                        if skip_reason
                        else resolve_section_approvers(section, applicant_id)
                    ),
                    role_id=role.pk,
                    history_scope=role.history_scope,
                    handles_cancellation=role.handles_cancellation,
                    section_id=section.pk,
                    skipped=bool(skip_reason),
                    skip_reason=skip_reason,
                )
            )

        if applicant_order is not None and applicant_order == sections[-1].order:
            # The applicant holds the last step, so there is no higher stage to
            # send this to. Hand it to HR rather than refusing it or, worse,
            # letting it be finalised by nobody.
            definitions.append(_hr_review_stage(sections[-1].order + 1, applicant_id))
        return definitions


def _applicant_section_order(sections, applicant_id) -> int | None:
    """The order of the stage the applicant would have to act on alone, if any.

    At most one, because ``section_workflow_approver_unique`` (Unit 30) puts an
    employee on one stage per workflow. That is what makes the skip-forward
    decision a single comparison rather than a search for a safe landing point.

    "Would have to act on" is resolved the same way :func:`resolve_section_approvers`
    resolves the stage -- the configured approver, or the sole institution-wide
    holder when the section is unstaffed -- so the applicant is recognised as
    holding a stage whether they were appointed to it directly or reached it
    through a role's fallback.
    """
    if applicant_id is None:
        return None
    for section in sections:
        if _section_candidate_ids(section) == {applicant_id}:
            return section.order
    return None


def _section_candidate_ids(section) -> set[int]:
    """Every active person who could act on ``section``, applicant included.

    The pre-exclusion view of a stage. Used only to recognise the applicant's own
    stage; a stage that resolves to nobody is not the applicant's to skip, and
    still fails the ordinary configuration check naming the section.

    Resolved through :func:`resolve_section_approvers` itself rather than
    alongside it, so the skip-forward decision and the routing decision can
    never disagree about who holds a step — a wide holding that resolves a stage
    is exactly the case where two implementations would have drifted.
    """
    try:
        return set(resolve_section_approvers(section))
    except WorkflowConfigError:
        return set()


def _skip_reason_for(section, applicant_order: int | None) -> str:
    """Why this stage is skipped for this applicant, or ``""`` to route to it.

    Two different reasons, because they answer different questions for whoever
    reads the history: their own stage is skipped because an approver cannot
    approve their own leave, and a stage below it is skipped because the applicant
    outranks it.
    """
    if applicant_order is None:
        return ""
    if section.order == applicant_order:
        return "Applicant cannot approve their own application."
    if section.order < applicant_order:
        return "Applicant is a higher-stage approver."
    return ""


def _hr_review_stage(order: int, applicant_id: int | None) -> StageDefinition:
    """The HR destination for an application that has no team stage left.

    Modelled as one more stage rather than a flag on the application, so HR's
    authority, the approval history, and the decision path are the ones that
    already exist: ``get_decision_authority`` resolves through
    ``user_may_act`` -> the ``eligible_approvers`` snapshot, exactly as it does
    for a team's stage. Approving it finalises; rejecting it rejects.

    The applicant is excluded from the eligible set. If that leaves nobody — the
    only HR account belongs to the person applying — the submission is refused
    rather than parked on a stage nobody can act on.
    """
    hr_ids = list(
        User.objects.filter(role=User.Role.HR, is_active=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    eligible = [pk for pk in hr_ids if pk != applicant_id]
    if not eligible:
        raise WorkflowConfigError(
            "This employee's own position is the final approval step, so their "
            "application goes to Human Resources to be decided. No other active "
            "HR account is available to decide it. Ask HR to add an HR account, "
            "or to appoint another approver to the final step, before this "
            "application is submitted."
        )
    return StageDefinition(
        order=order,
        role="hr",
        role_label="Human Resources",
        approver_user_ids=tuple(eligible),
        role_id=None,
        # HR is the oversight role: it reviews across teams, so its stage
        # carries the broadest scope rather than the narrowest default.
        history_scope=ApproverRole.HistoryScope.ALL,
        handles_cancellation=False,
        section_id=None,
    )


def _chain_cycle(application) -> int:
    from django.db.models import Min

    return (
        application.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
    )
