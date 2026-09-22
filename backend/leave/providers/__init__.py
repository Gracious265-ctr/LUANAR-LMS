"""Rules-provider entry points for leave validation (Unit 14).

``get_provider`` instantiates the class named by ``settings.LEAVE_RULES_PROVIDER``
(no arguments). ``get_today`` is the single clock seam: every "today" in the
pipeline goes through it so tests can patch one function instead of the clock.
"""

from importlib import import_module

from django.conf import settings
from django.utils import timezone


def get_provider():
    """Return an instance of the configured ``LEAVE_RULES_PROVIDER``."""
    module_path, _, class_name = settings.LEAVE_RULES_PROVIDER.rpartition(".")
    module = import_module(module_path)
    provider_class = getattr(module, class_name)
    return provider_class()


def get_today():
    """Return today's date in the configured timezone (Africa/Blantyre)."""
    return timezone.localdate()