"""Workflow provider contract and real implementation (Unit 16, Unit 21).

The workflow provider resolves the ordered approver chain (stage definitions)
for a submitted leave application. It is the single point of swappability:
:func:`get_workflow_provider` reads ``settings.WORKFLOW_PROVIDER``.

The default is :class:`DatabaseWorkflowProvider`, which resolves the applicant's
**team** to the one workflow that team uses, and maps its ``Section`` rows into
``StageDefinition`` objects. Each section's approvers are found by
:func:`resolve_section_approvers`: the section's active members with the applicant
removed, or — only when the section has no members and its role is
institution-wide — the role's single institution-wide holder. A section is a set
of people rather than one, because the application is decided by whichever member
acts first. The provider is pure data (no writes): it returns
planned stages only. The assignment service
(``workflows.services.assign_workflow``) validates them and materialises them as
``ApplicationStage`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from users.models import User

from .models import ApproverRole, RoleAssignment, SectionMember, Team


class WorkflowConfigError(ValueError):
    """Raised when a workflow definition is malformed or unsatisfiable."""


@dataclass(frozen=True)
class StageDefinition:
    """One planned stage returned by a workflow provider.

    ``approver_user_ids`` is the set of people entitled to act on the stage — a
    section is resolved by whoever acts first, so it is a set, not a person. It
    is never empty: a section nobody can act for is a configuration error and is
    refused at resolution time rather than routed to a fallback (invariant 12.7).
    """

    order: int
    role: str
    role_label: str
    approver_user_ids: tuple[int, ...] = ()
    role_id: int | None = None
    history_scope: str | None = None
    handles_cancellation: bool = False
    section_id: int | None = None


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


def _employee_key(application: Any) -> tuple[str, str]:
    """The (category, department) pair the workflow scope matches against."""
    profile = getattr(application.employee, "employee_profile", None)
    if profile is None:
        return ("", "")
    return (profile.category, (profile.department or "").strip())


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


def resolve_section_approvers(section, applicant_id: int | None = None) -> tuple[int, ...]:
    """The people entitled to act for ``section``, or raise.

    The single authoritative resolution algorithm:

    1. The section's active members, minus the applicant. A section may name any
       number of members, and the application is decided by whichever of them
       acts first — so this is a set and its size is not a defect. The applicant
       is removed here, at resolution time, so an approver can never be the
       approver of their own leave no matter which surface asks later
       (invariant 12.3).
    2. Only when the section has no member **at all** and its role is
       institution-wide does the global holder decide — and then there must be
       exactly one, because a global fallback is not a race anyone can see.
    3. Otherwise the configuration is incomplete and the submission is refused.

    The applicant exclusion in step 1 deliberately does not change *which* branch
    is taken. A section whose only member is the applicant is a section that has
    a member, so it does not fall through to the global holder: falling through
    would hand the applicant's own leave to a global holder who may be the very
    person who was excluded, or would let a global holder approve for a step HR
    deliberately staffed. The "only member is the applicant" case therefore gets
    its own error naming the real fix.

    Only memberships **in force today** are considered. A membership dated into
    the future is a handover HR has scheduled, and a membership that has been
    closed is history: routing to either would hand an approval to somebody who
    was not, or is not yet, an approver for that step.

    Every error names the role, names the section, and says what HR has to do
    about it.
    """
    all_members = tuple(
        SectionMember.objects.effective_on()
        .filter(section=section, user__is_active=True)
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )
    if not all_members:
        role = section.approver_role
        if role.is_institution_wide:
            holders = _institution_wide_holder_ids(role)
            if len(holders) == 1:
                return (holders[0],)
            if not holders:
                raise WorkflowConfigError(
                    f'The "{section.name}" section has no members, and the '
                    f"{role.label} role has no active holder. Add someone to the "
                    "section, or ask HR to assign one."
                )
            raise WorkflowConfigError(
                f'The "{section.name}" section has no members, and the '
                f"{role.label} role has multiple active holders. Add someone to "
                "the section, or ask HR to designate exactly one."
            )
        raise WorkflowConfigError(
            f'The "{section.name}" section has no members. Add at least one '
            "person who can act for it."
        )

    members = all_members
    if applicant_id is not None:
        members = tuple(uid for uid in members if uid != applicant_id)
    if members:
        return members

    raise WorkflowConfigError(
        f'The only member of the "{section.name}" section is the applicant '
        "themself, and an approver cannot approve their own leave. Add "
        "another member to the section, or ask Human Resources to appoint "
        "them to a different approver role."
    )


def resolve_applicable_workflow(application: Any):
    """The active HR workflow governing ``application``, or ``None``.

    Scope precedence against the employee's (category, department) — blank
    scope means "any" (D5): exact ``(category, department)`` wins, then
    ``(category, any)``, then ``(any, department)``, then ``(any, any)``.
    Only ``is_active`` workflows with ``effective_from <= today`` apply; ties
    within a bucket break to the earliest effective date.

    Retained for reference only: routing is team-based (see
    :class:`DatabaseWorkflowProvider`) and no longer calls this.
    """
    from django.db.models import Q

    from .models import Workflow

    category, department = _employee_key(application)
    today = timezone.localdate()
    base = Workflow.objects.filter(
        is_active=True, effective_from__isnull=False, effective_from__lte=today
    )
    for query in (
        Q(employee_category=category, department=department),
        Q(employee_category=category, department=""),
        Q(employee_category="", department=department),
        Q(employee_category="", department=""),
    ):
        candidate = (
            base.filter(query)
            .order_by("effective_from", "id")
            .only("pk", "name")
            .first()
        )
        if candidate is not None:
            return candidate
    return None


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
        from .models import ApplicationStage

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
        ``assigned_approver``: a section is resolved by whoever acts first, so
        ``assigned_approver`` is null until somebody does and would leave the
        undecided members of every chain out of the recipient list.
        """
        from .models import ApplicationStage, ApplicationStageApprover

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
    each section's members are resolved to a set of people by
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
        if team.status == Team.Status.DRAFT:
            raise WorkflowConfigError(
                f"The {team.name} team is still being set up. Ask HR to finish "
                "configuring it and activate it."
            )
        if team.status == Team.Status.INACTIVE:
            raise WorkflowConfigError(
                f"The {team.name} team is inactive. Ask HR to activate it, or to "
                "move the employee to an active team."
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
                f"Workflow '{workflow.name}' is inactive. Ask HR to activate it, "
                f"or to point the {team.name} team at an active workflow."
            )
        if (
            workflow.effective_from is not None
            and workflow.effective_from > timezone.localdate()
        ):
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' does not start until "
                f"{workflow.effective_from.isoformat()}. Ask HR to activate it "
                "earlier, or to point the team at an active workflow."
            )

        sections = list(
            workflow.sections.filter(is_active=True)
            .order_by("order")
            .select_related("approver_role")
            .prefetch_related("members__user")
        )
        if not sections:
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' has no active approval sections."
            )

        applicant_id = getattr(application, "employee_id", None)
        definitions: list[StageDefinition] = []
        for section in sections:
            role = section.approver_role
            definitions.append(
                StageDefinition(
                    order=section.order,
                    role=role.code,
                    role_label=role.label,
                    approver_user_ids=resolve_section_approvers(
                        section, applicant_id
                    ),
                    role_id=role.pk,
                    history_scope=role.history_scope,
                    handles_cancellation=role.handles_cancellation,
                    section_id=section.pk,
                )
            )
        return definitions


def _chain_cycle(application) -> int:
    from django.db.models import Min

    return (
        application.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
    )
