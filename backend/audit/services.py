"""Audit logging shared by the serializers, services, and views that own actions."""

import math
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from audit.models import AuditEntry
from users.models import User


def current_actor(serializer) -> User | None:
    """The authenticated actor from a DRF serializer's request context."""
    request = serializer.context.get("request")
    return getattr(request, "user", None)


#: Displayed in place of a person when an entry has no human actor.
SYSTEM_ACTOR_NAME = "System"


def actor_display_name(actor) -> str:
    """The display name for an audit entry's actor, or ``System`` when there is none.

    ``AuditEntry.actor`` is nullable by design: an action taken by the system
    rather than a person (Unit 23b's background document render, whether it
    succeeded or failed) is recorded with no actor. Every reader of an entry must
    go through here so a system entry renders as ``System`` instead of raising
    ``AttributeError`` on ``None`` — the approver review payload did exactly
    that, which turned one failed document render into a 500 on the review page.
    """
    if actor is None:
        return SYSTEM_ACTOR_NAME
    return actor.get_full_name() or actor.username


def _jsonable(value):
    """Recursively convert values to JSON-field-safe primitives.

    PostgreSQL's psycopg adapter serializes JSON with the standard ``json``
    encoder, so dates, datetimes, UUIDs and Decimals nested in ``detail`` must
    be converted here (DjangoJSONEncoder does not apply).

    ``Decimal`` becomes a string, which is how the balance ledger already
    records its days by hand. Anything else unrecognised is stringified rather
    than passed through: ``json.dumps`` raises ``TypeError`` on an object it
    cannot encode, and because an audit entry is written inside the owning
    business transaction, that failure would roll the business write back with
    it. A value nobody thought to convert is not worth losing an approval over,
    and ``str()`` keeps it legible in the trail. Non-finite floats are
    stringified for the same reason from the other direction: ``json.dumps``
    *does* emit ``NaN``, which PostgreSQL's ``jsonb`` then rejects.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


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