"""Tracking-provider interface (Unit 15).

Follows the same wiring pattern as the Unit 14 rules provider: a dotted-path
setting resolved once through a small factory. ``settings.LEAVE_TRACKING_PROVIDER``
names ``FixtureTrackingProvider`` until Unit 20 replaces it with a provider
backed by the real workflow tables.
"""

from abc import ABC, abstractmethod
from importlib import import_module

from django.conf import settings

from .contracts import WorkflowTracking


class TrackingProvider(ABC):
    @abstractmethod
    def get_workflow_tracking(self, application) -> WorkflowTracking:
        """Return workflow state for an already-authorized, already-submitted application.

        Must use the workflow snapshot the application was submitted with,
        never the current workflow configuration (invariant 12.5).
        """


def get_tracking_provider() -> TrackingProvider:
    """Return an instance of the configured ``LEAVE_TRACKING_PROVIDER``."""
    module_path, _, class_name = settings.LEAVE_TRACKING_PROVIDER.rpartition(".")
    module = import_module(module_path)
    provider_class = getattr(module, class_name)
    return provider_class()