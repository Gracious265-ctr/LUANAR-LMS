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


class WorkflowProvider(Protocol):
    """The interface every workflow provider must satisfy."""

    def get_stage_definitions(self, application: Any) -> list[StageDefinition]: ...


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