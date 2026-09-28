"""Workflow provider contract and real implementation (Unit 16, Unit 21).

The workflow provider resolves the ordered approver chain (stage definitions)
for a submitted leave application. It is the single point of swappability:
:func:`get_workflow_provider` reads ``settings.WORKFLOW_PROVIDER``.

The default is :class:`DatabaseWorkflowProvider`, which resolves the applicant's
**team** to the one workflow that team uses, and maps its ``WorkflowStage`` rows
into ``StageDefinition`` objects. Each stage's approver is found by
:func:`resolve_stage_approver`: the team member holding that role, or — only when
the team has none and the role is institution-wide — the role's single
institution-wide holder. The provider is pure data (no writes): it returns
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

from .models import ApproverRole, RoleAssignment, TeamMember


class WorkflowConfigError(ValueError):
    """Raised when a workflow definition is malformed or unsatisfiable."""


@dataclass(frozen=True)
class StageDefinition:
    """One planned stage returned by a workflow provider."""

    order: int
    role: str
    role_label: str
    approver_user_id: int | None = None
    role_id: int | None = None
    history_scope: str | None = None
    handles_cancellation: bool = False


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
    approver_user_id: int | None = None


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


def resolve_stage_approver(role: ApproverRole, team) -> int:
    """The user who approves ``role`` for a member of ``team``, or raise.

    The single authoritative resolution algorithm:

    1. The team's member holding the role wins whenever there is one. The
       ``(team, role)`` unique constraint guarantees at most one, so team
       membership is unambiguous.
    2. Only when the team has no member for the role, and the role is
       institution-wide, does the global holder decide — and then there must be
       exactly one.
    3. Otherwise the configuration is incomplete and the submission is refused.

    Every error names the role, names the team where one exists, and says what
    HR has to do about it.
    """
    membership = TeamMember.objects.filter(team=team, role=role).select_related(
        "user"
    ).first()
    if membership is not None:
        return membership.user_id

    if role.is_institution_wide:
        holders = _institution_wide_holder_ids(role)
        if len(holders) == 1:
            return holders[0]
        if not holders:
            raise WorkflowConfigError(
                f"The {role.label} role has no active holder. Ask HR to assign one."
            )
        raise WorkflowConfigError(
            f"The {role.label} role has multiple active holders. Ask HR to "
            "designate exactly one."
        )

    raise WorkflowConfigError(
        f"The {role.label} role has no holder on the {team.name} team. Add a "
        "member with this role, or make the role institution-wide."
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
        """
        from .models import ApplicationStage

        stages = (
            ApplicationStage.objects.filter(
                application=application,
                submission_cycle=_chain_cycle(application),
                handles_cancellation=True,
            )
            .order_by("stage_order")
            .only(
                "stage_order",
                "role",
                "role_label",
                "assigned_approver_id",
            )
        )
        return [
            CancellationStageSpec(
                order=stage.stage_order,
                role=stage.role,
                role_label=stage.role_label or stage.role,
                approver_user_id=stage.assigned_approver_id,
            )
            for stage in stages
        ]

    def get_workflow_member_user_ids(self, application: Any) -> list[int]:
        """Every user in the original workflow snapshot (event recipients)."""
        from .models import ApplicationStage

        return list(
            ApplicationStage.objects.filter(
                application=application,
                submission_cycle=_chain_cycle(application),
            )
            .order_by("stage_order")
            .values_list("assigned_approver_id", flat=True)
        )


class DatabaseWorkflowProvider(SnapshotStagesMixin):
    """Workflow provider backed by the real HR team and role configuration.

    The applicant's :class:`~workflows.models.Team` names the workflow; the
    workflow's ordered stages name the roles; and each role is resolved to a
    person by :func:`resolve_stage_approver`.
    """

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]:
        team = _employee_team(application)
        if team is None:
            raise WorkflowConfigError(
                "This employee is not in a team. Ask HR to assign them to a team "
                "before they submit a leave application."
            )
        if not team.is_active:
            raise WorkflowConfigError(
                f"The {team.name} team is inactive. Ask HR to activate it, or to "
                "move the employee to an active team."
            )
        workflow = team.workflow
        if workflow is None:
            raise WorkflowConfigError(
                f"The {team.name} team has no approval workflow. Ask HR to set "
                "one on the team."
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

        stages = list(
            workflow.stages.order_by("order").select_related("approver_role")
        )
        if not stages:
            raise WorkflowConfigError(
                f"Workflow '{workflow.name}' has no approval stages."
            )

        definitions: list[StageDefinition] = []
        for stage in stages:
            role = stage.approver_role
            definitions.append(
                StageDefinition(
                    order=stage.order,
                    role=role.code,
                    role_label=role.label,
                    approver_user_id=resolve_stage_approver(role, team),
                    role_id=role.pk,
                    history_scope=role.history_scope,
                    handles_cancellation=role.handles_cancellation,
                )
            )
        return definitions


def _chain_cycle(application) -> int:
    from django.db.models import Min

    return (
        application.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
    )
