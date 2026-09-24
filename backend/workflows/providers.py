"""Swappable approval-workflow provider (Unit 16).

Follows the already-established wiring pattern (rules provider, tracking
provider): the decision logic depends only on this ``WorkflowProvider``
protocol, and the class actually used is selected by ``settings.WORKFLOW_PROVIDER``.
``FixtureWorkflowProvider`` is the placeholder until Unit 20 drops in the real
Unit 6 workflow store without touching the decision service.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from django.conf import settings


@dataclass(frozen=True)
class StageDefinition:
    """One ordered approval step produced by a provider for an application."""

    order: int
    role: str
    role_label: str
    approver_user_id: int


@dataclass(frozen=True)
class StageSpec:
    """One cancellation approval stage (Unit 18, section 3.2).

    Roles are restricted to Supervisor/HOD by contract (rule 2.1.4); the
    provider preserves the original workflow order. ``approver_user_id`` is the
    specific bound user (as in Unit 16 stage snapshots), never a role query on
    the fly at request time.
    """

    order: int
    role: str
    approver_user_id: int


class WorkflowProvider(Protocol):
    """Interface the assignment service resolves stages through."""

    def get_stage_definitions(self, application) -> list[StageDefinition]: ...

    def get_cancellation_stages(self, application) -> list[StageSpec]:
        """Return the Supervisor/HOD approval stages for a cancellation.

        Derived from the application's **original workflow snapshot**, filtered
        to Supervisor/HOD roles, original order preserved. Empty when the
        snapshot has no such stage (the request is then refused with
        ``no_cancellation_approvers``; no silent fallback).
        """

    def get_workflow_member_user_ids(self, application) -> list[int]:
        """Return every approver user id in the application's snapshot.

        Used as domain-event recipients for cancellations.
        """


def get_workflow_provider() -> WorkflowProvider:
    """Return an instance of the configured ``WORKFLOW_PROVIDER``."""
    module_path, _, class_name = settings.WORKFLOW_PROVIDER.rpartition(".")
    module = import_module(module_path)
    provider_class = getattr(module, class_name)
    return provider_class()