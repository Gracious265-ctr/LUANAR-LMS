"""Domain-event dispatcher (Unit 22).

``dispatch`` is the single entry point the domain modules call (approval,
cancellation, delegation, reassignment). It is resolved through
``settings.NOTIFICATION_DISPATCHER``:

- ``"off"``  → no-op (the test-suite default; the subscription code is still
  exercised by the Unit 22 tests via ``override_settings``).
- ``"on"`` (default) → the bundled ``notifications.subscribers`` handler.
- any other dotted path → that module's callable, for custom routing.

``dispatch`` always returns ``None`` so the existing side-effect-free event
contracts (e.g. the Unit 16 approval test that asserts ``emit_approval_event``
returns ``None``) hold even when notifications are enabled.
"""

from importlib import import_module

from django.conf import settings


def dispatch(kind: str, event) -> None:
    """Route ``event`` to the configured subscriber for ``kind``."""
    setting = (getattr(settings, "NOTIFICATION_DISPATCHER", "on") or "on").strip()
    if setting == "off":
        return None
    handler = _resolve(setting)
    if handler is None:
        return None
    handler(kind, event)
    return None


def _resolve(setting: str):
    if setting in ("", "on"):
        from . import subscribers

        return getattr(subscribers, "on_domain_event", None)
    module_path, _, name = setting.rpartition(".")
    module = import_module(module_path)
    return getattr(module, name)