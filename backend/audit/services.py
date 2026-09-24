"""Thin audit-writing helpers used across units.

``record_event`` is the single writer for the :class:`~audit.models.AuditEvent`
trail (Unit 14 onward). The ``record_config_change`` wrapper is the preferred
entry point for Unit 11's HR-configuration actions: it packages the human
summary, optional reason, and before/after diff into ``metadata`` so the HR
Audit view can render one consistent shape.
"""

from datetime import date, datetime
from uuid import UUID

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


def target_summary(instance) -> str:
    """A short human-readable description of ``instance`` for audit metadata."""
    reference = getattr(instance, "reference_number", None)
    if reference:
        return str(reference)
    return str(instance)


def _jsonable(value):
    """Recursively convert values to JSON-field-safe primitives.

    PostgreSQL's psycopg adapter serializes JSON with the standard ``json``
    encoder, so dates, datetimes, and UUIDs nested in ``metadata`` must be
    converted here (DjangoJSONEncoder does not apply to JSONField payloads).
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def changed_fields(
    before: dict, after: dict, keys: list[str] | None = None
) -> dict:
    """The before/after values for the fields that actually changed.

    Returns ``{"before": {...}, "after": {...}}`` limited to the fields whose
    values differ. ``keys`` limits comparison when the caller only cares about
    a subset. Values that compare equal on both sides are omitted.
    """
    before = before or {}
    after = after or {}
    compare_keys = keys or sorted(set(before) | set(after))
    changed_before: dict = {}
    changed_after: dict = {}
    for key in compare_keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changed_before[key] = _jsonable(old)
            changed_after[key] = _jsonable(new)
    return {"before": changed_before, "after": changed_after}


def record_config_change(
    *,
    actor,
    action: str,
    target,
    summary: str = "",
    before: dict | None = None,
    after: dict | None = None,
    reason: str = "",
    prev_state: str = "",
    new_state: str = "",
) -> AuditEvent:
    """Record an HR-configuration change with a display-ready metadata shape.

    ``metadata`` becomes ``{"summary", "reason", "before", "after"}`` (empty
    pieces omitted). On a create (``before is None``) only ``after`` is kept;
    otherwise both snapshots are reduced to the fields that changed. Action
    codes are caller-built (e.g. ``"employee.updated"``).
    """
    metadata: dict = {}
    summary = (summary or target_summary(target)).strip()
    if summary:
        metadata["summary"] = summary
    reason = (reason or "").strip()
    if reason:
        metadata["reason"] = reason
    if before is None and after is not None:
        metadata["before"] = None
        metadata["after"] = _jsonable(after)
    elif before is not None and after is not None:
        diff = changed_fields(before, after)
        if diff["before"] or diff["after"]:
            metadata["before"] = diff["before"]
            metadata["after"] = diff["after"]

    return record_event(
        actor=actor,
        action=action,
        target=target,
        prev_state=prev_state,
        new_state=new_state,
        metadata=metadata,
    )


def current_actor(serializer) -> "User | None":  # noqa: F821
    """The authenticated actor from a DRF serializer's request context."""
    request = serializer.context.get("request")
    return getattr(request, "user", None)


def events_for_target(instance) -> list[AuditEvent]:
    """Every :class:`AuditEvent` whose target is ``instance``, oldest first."""
    content_type = ContentType.objects.get_for_model(instance)
    return list(
        AuditEvent.objects.filter(
            content_type=content_type,
            object_id=str(instance.pk),
        ).order_by("created_at")
    )
