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


class WorkflowProvider(Protocol):
    """Interface the assignment service resolves stages through."""

    def get_stage_definitions(self, application) -> list[StageDefinition]: ...


def get_workflow_provider() -> WorkflowProvider:
    """Return an instance of the configured ``WORKFLOW_PROVIDER``."""
    module_path, _, class_name = settings.WORKFLOW_PROVIDER.rpartition(".")
    module = import_module(module_path)
    provider_class = getattr(module, class_name)
    return provider_class()