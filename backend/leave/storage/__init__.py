"""Document storage-backend entry point (Unit 19).

``get_storage_backend`` instantiates the class named by
``settings.LEAVE_STORAGE_BACKEND`` (dotted path, no arguments), mirroring the
``leave.providers.get_provider`` factory pattern.
"""

from importlib import import_module

from django.conf import settings


def get_storage_backend():
    """Return an instance of the configured ``LEAVE_STORAGE_BACKEND``."""
    module_path, _, class_name = settings.LEAVE_STORAGE_BACKEND.rpartition(".")
    module = import_module(module_path)
    backend_class = getattr(module, class_name)
    return backend_class()