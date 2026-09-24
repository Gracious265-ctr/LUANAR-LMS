"""Workflow provider contract and fixture implementation (Unit 16).

The workflow provider resolves the ordered approver chain (stage definitions)
for a submitted leave application. It is the single point of swappability:
:func:`get_workflow_provider` reads ``settings.WORKFLOW_PROVIDER``, and the
fixture provider below is replaced by the real HR-track provider in a later
unit without touching the approval services.

The provider is pure data (no writes): it returns planned stages only. The
assignment service (``workflows.services.assignment``) validates them and
materialises them as ``ApplicationStage`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from users.models import EmployeeProfile, User

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
    roles, in original order. Reconciliation with the real Unit 6 contract
    happens at Unit 20.
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
    """The (category, department) key pair the fixture maps by."""
    profile = getattr(application.employee, "employee_profile", None)
    if profile is None:
        return ("", "")
    return (profile.category, profile.department)


FIXTURE_WORKFLOWS: dict[tuple[str, str], tuple[str, ...]] = {
    # (category, department) -> chain of stage roles, first to last.
    ("", ""): ("supervisor", "hod", "registrar", "dvc"),
    ("academic", ""): ("hod", "dean", "registrar", "dvc"),
    ("administration", ""): ("supervisor", "hod", "registrar", "dvc"),
    ("academic", "Bunda College"): ("supervisor", "hod", "registrar", "dvc"),
    ("academic", "Faculty of Agriculture"): ("supervisor", "hod", "registrar", "dvc"),
}


class FixtureWorkflowProvider:
    """Fixture workflow provider.

    Chain lookup is scoped by employee category/department: the most specific
    key wins, and an empty key applies as a fallback. Approver users are the
    lowest-id active user of each role, mirroring the fixture-rules convention.

    Unit 18 extension: cancellation stages and workflow membership are read from
    the application's materialised ``ApplicationStage`` snapshot (the chain that
    was created at submission and reused across resubmissions). Reconciliation
    with the real Unit 6 workflow contract happens at Unit 20.
    """

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]:
        key = _employee_key(application)
        for candidate in (key, (key[0], ""), ("", "")):
            if candidate in FIXTURE_WORKFLOWS:
                roles = FIXTURE_WORKFLOWS[candidate]
                break
        else:
            raise WorkflowConfigError(
                f"No workflow configured for category/department {key!r}."
            )

        definitions: list[StageDefinition] = []
        for order, role in enumerate(roles, start=1):
            try:
                role_label = STAGE_ROLE_LABELS[role]
            except KeyError:
                raise WorkflowConfigError(f"Unknown stage role {role!r}.")
            definitions.append(
                StageDefinition(
                    order=order,
                    role=role,
                    role_label=role_label,
                    approver_user_id=_first_active_user_id(role),
                )
            )
        return definitions

    def get_cancellation_stages(
        self, application: Any
    ) -> list[CancellationStageSpec]:
        """The Supervisor/HOD stages of the application's original snapshot.

        Reads the materialised stage chain (``workflow_chain_cycle``) so later
        workflow configuration changes never affect a cancellation.
        """
        from .models import ApplicationStage, STAGE_ROLE_LABELS as _labels

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
                role_label=stage.role_label or _labels.get(stage.role, stage.role),
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


def _chain_cycle(application) -> int:
    from django.db.models import Min

    return (
        application.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
    )