"""Audit logging shared by the serializers, services, and views that own actions."""

from datetime import date, datetime
from uuid import UUID

from audit.models import AuditEntry
from users.models import User


def current_actor(serializer) -> User | None:
    """The authenticated actor from a DRF serializer's request context."""
    request = serializer.context.get("request")
    return getattr(request, "user", None)


def _jsonable(value):
    """Recursively convert values to JSON-field-safe primitives.

    PostgreSQL's psycopg adapter serializes JSON with the standard ``json``
    encoder, so dates, datetimes, and UUIDs nested in ``detail`` must be
    converted here (DjangoJSONEncoder does not apply).
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


def record_audit(
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id,
    target_summary: str,
    detail: dict | None = None,
    reason: str = "",
) -> AuditEntry:
    """Persist one append-only audit entry.

    ``target_id`` may be an int or uuid string and is normalized to text.
    ``detail`` is stored as given (callers build ``{"before": ..., "after": ...}``
    for configuration/state changes); non-serializable values are normalized to
    JSON-safe primitives. Returns the created entry.
    """
    return AuditEntry.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        target_summary=(target_summary or "").strip(),
        detail=_jsonable(detail) if detail is not None else None,
        reason=(reason or "").strip(),
    )


def changed_fields(
    before: dict, after: dict, keys: list[str] | None = None
) -> dict:
    """The before/after values for the fields that actually changed.

    Returns ``{"before": {...}, "after": {...}}`` limited to the fields whose
    values differ. ``keys`` limits comparison when the caller only cares about a
    subset. Values that compare equal on both sides are omitted.
    """
    before = before or {}
    after = after or {}
    compare_keys = keys or list(before.keys()) + list(after.keys())
    changed_before: dict = {}
    changed_after: dict = {}
    for key in compare_keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changed_before[key] = old
            changed_after[key] = new
    return {"before": changed_before, "after": changed_after}