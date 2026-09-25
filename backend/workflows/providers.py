"""Workflow provider contract and real implementation (Unit 16, Unit 21).

The workflow provider resolves the ordered approver chain (stage definitions)
for a submitted leave application. It is the single point of swappability:
:func:`get_workflow_provider` reads ``settings.WORKFLOW_PROVIDER``.

Since Unit 21 the default is :class:`DatabaseWorkflowProvider`, which resolves
the applicable :class:`~workflows.models.Workflow` HR configured for the
employee's category/department and maps its ``WorkflowStage`` rows into
``StageDefinition`` objects (approver = the lowest-id active user of the stage
role). The provider is pure data (no writes): it returns planned stages only.
The assignment service (``workflows.services.assign_workflow``) validates them
and materialises them as ``ApplicationStage`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from users.models import User

from .models import STAGE_ROLE_LABELS


class WorkflowConfigError(ValueError):
    """Raised when a workflow definition is malformed or unsatisfiable."""


@dataclass(frozen=True)
class StageDefinition:
    """One planned stage returned by a workflow provider."""

    order: int
    role: str
    role_label: str
    approver_user_id: int | None = None


@dataclass(frozen=True)
class CancellationStageSpec:
    """One planned cancellation stage (Unit 18, spec 3.2).

    Built from the application's *original* workflow snapshot (the materialised
    stage chain under ``workflow_chain_cycle``), filtered to Supervisor/HOD
    roles, in original order. Snapshot reads are provider-agnostic, so a later
    workflow configuration change never affects a cancellation.
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


def _first_active_user_id(role: str) -> int | None:
    """The lowest-id active user holding ``role``, if any."""
    return (
        User.objects.filter(role=role, is_active=True)
        .order_by("id")
        .values_list("id", flat=True)
        .first()
    )


def _employee_key(application: Any) -> tuple[str, str]:
    """The (category, department) pair the workflow scope matches against."""
    profile = getattr(application.employee, "employee_profile", None)
    if profile is None:
        return ("", "")
    return (profile.category, (profile.department or "").strip())


def resolve_applicable_workflow(application: Any):
    """The active HR workflow governing ``application``, or ``None``.

    Scope precedence against the employee's (category, department) — blank
    scope means "any" (D5): exact ``(category, department)`` wins, then
    ``(category, any)``, then ``(any, department)``, then ``(any, any)``.
    Only ``is_active`` workflows with ``effective_from <= today`` apply; ties
    within a bucket break to the earliest effective date.
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
        """The Supervisor/HOD stages of the application's original snapshot."""
        from .models import ApplicationStage

        stages = (
            ApplicationStage.objects.filter(
                application=application,
                submission_cycle=_chain_cycle(application),
                role__in=("supervisor", "hod"),
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
                role_label=stage.role_label or STAGE_ROLE_LABELS.get(stage.role, stage.role),
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
    """Workflow provider backed by the real HR workflow configuration.

    Resolves the applicable :class:`Workflow` for the application's
    category/department (case-insensitive on the free-text department), then
    maps its ordered ``WorkflowStage`` rows to definitions. Each stage's
    approver is the lowest-id active user holding that role, matching the
    fixture-provider convention the approval chain already assumed.
    """

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]:
        workflow = resolve_applicable_workflow(application)
        if workflow is None:
            raise WorkflowConfigError(
                "No active workflow is configured for the employee's "
                "category/department."
            )

        stages = list(workflow.stages.order_by("order").only("order", "approver_role"))
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
                    role=role,
                    role_label=STAGE_ROLE_LABELS.get(role, role),
                    approver_user_id=_first_active_user_id(role),
                )
            )
        return definitions


def _chain_cycle(application) -> int:
    from django.db.models import Min

    return (
        application.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
    )