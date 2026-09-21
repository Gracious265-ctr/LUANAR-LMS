"""Thin audit-writing helpers used across units."""

from django.contrib.contenttypes.models import ContentType

from .models import AuditEvent


def record_event(
    *,
    actor,
    action: str,
    target,
    prev_state: str = "",
    new_state: str = "",
    metadata: dict | None = None,
) -> AuditEvent:
    """Append an :class:`AuditEvent` describing a change to ``target``.

    ``target`` is any model instance; its content type and primary key are
    stored so the event survives deletes. ``prev_state``/``new_state`` are
    short status strings (e.g. ``"draft"`` -> ``"submitted"``). Nothing here is
    ever updated or deleted after creation.
    """
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        content_type=ContentType.objects.get_for_model(target),
        object_id=target.pk,
        prev_state=prev_state or "",
        new_state=new_state or "",
        metadata=metadata or {},
    )