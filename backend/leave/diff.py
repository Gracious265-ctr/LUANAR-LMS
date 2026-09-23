"""Diff engine for resubmission change summaries (Unit 17, section 4).

``compute_changes`` is a pure, dependency-free function: given the content
snapshot of the previous revision and the application's current content, it
returns the ``Changes`` JSON shape the spec defines. It is used both when a
revision is created (at submit/resubmit) and for the live ``changes_preview``
on the edit page, so the preview always matches what the approver will see.
"""

from __future__ import annotations

from typing import Any

COMPARED_FIELDS: tuple[tuple[str, str], ...] = (
    ("leave_type", "Leave type"),
    ("start_date", "Start date"),
    ("end_date", "End date"),
    ("working_days", "Working days"),
    ("reason", "Reason"),
)

DOCUMENT_FIELDS = ("size_bytes", "content_type")


def _raw_value(snapshot: dict, field: str):
    """Value used to decide whether a field changed (leave_type compared by id)."""
    if field == "leave_type":
        leave_type = snapshot.get("leave_type") or {}
        return leave_type.get("id")
    return snapshot.get(field)


def _display_value(snapshot: dict, field: str, raw) -> Any:
    """Value surfaced to the UI (leave_type labelled by name; dates as ISO strings)."""
    if field == "leave_type":
        leave_type = snapshot.get("leave_type") or {}
        return leave_type.get("name") or raw
    if field in ("start_date", "end_date") and raw is not None:
        return raw.isoformat() if hasattr(raw, "isoformat") else str(raw)
    return raw


def _trim(value):
    return (value or "").strip()


def _show_as_field_change(field: str, before, after) -> bool:
    if field == "reason":
        return _trim(before) != _trim(after)
    return before != after


def compute_changes(previous_snapshot: dict, current_snapshot: dict) -> dict:
    """Compute the change summary between two content snapshots.

    Returns the ``{has_changes, fields, documents}`` shape from section 4.
    Field values are the snapshot values surfaced to the UI: dates as ISO
    strings, working days as an int, reason as text, and leave type as its
    *name* (comparison uses the id). The UI renders ``before``/``after``.

    Documents: previous documents are matched by ``document_id``. A previous
    document that is no longer active in the current snapshot is **replaced**
    when its ``replaced_by`` chain (crawled through the current snapshot's
    ``retired`` map) ends on a currently active document, otherwise **removed**.
    A currently active document absent from the previous snapshot is **added**
    unless it is the endpoint of a replacement chain.
    """
    fields: list[dict[str, Any]] = []
    for field, label in COMPARED_FIELDS:
        before_raw = _raw_value(previous_snapshot, field)
        after_raw = _raw_value(current_snapshot, field)
        if _show_as_field_change(field, before_raw, after_raw):
            fields.append(
                {
                    "field": field,
                    "label": label,
                    "before": _display_value(previous_snapshot, field, before_raw),
                    "after": _display_value(current_snapshot, field, after_raw),
                }
            )

    documents = _diff_documents(
        _previous_documents(previous_snapshot),
        current_snapshot,
    )

    has_changes = bool(fields) or any(
        documents[key] for key in ("added", "removed", "replaced")
    )

    return {
        "has_changes": has_changes,
        "fields": fields,
        "documents": documents,
    }


def _previous_documents(snapshot: dict) -> list[dict]:
    return [dict(item) for item in (snapshot.get("documents") or [])]


def _current_documents(snapshot: dict) -> list[dict]:
    return [dict(item) for item in (snapshot.get("documents") or [])]


def _retired_map(snapshot: dict) -> dict[str, dict]:
    """Map retired document id → retire record for the current snapshot."""
    return {
        str(item["document_id"]): dict(item)
        for item in (snapshot.get("retired") or [])
    }


def _chain_ends_on_active(document_id: str, retired: dict, active_ids: set[str]) -> str | None:
    """Follow ``replaced_by_id`` from ``document_id`` to its chain endpoint.

    Returns the active endpoint document ID when the chain terminates on a
    currently active document, ``None`` when the chain is broken or
    terminates on a retired document.
    """
    seen: set[str] = set()
    current: Any = document_id
    while True:
        current = str(current)
        if current in active_ids:
            return current
        if current in seen:
            return None
        seen.add(current)
        record = retired.get(current)
        if record is None:
            return None
        next_id = record.get("replaced_by_id")
        if next_id is None:
            return None
        current = str(next_id)


def _diff_documents(previous: list[dict], current_snapshot: dict) -> dict:
    previous_by_id = {str(item["document_id"]): item for item in previous}
    current_active = _current_documents(current_snapshot)
    active_by_id = {str(item["document_id"]): item for item in current_active}
    retired = _retired_map(current_snapshot)

    active_ids = set(active_by_id)

    # Build the ``replaced`` list first: iterate retired documents that were
    # in the previous snapshot, follow their replacement chain to the active
    # endpoint, and record the old→new name pair.
    replaced: list[dict] = []
    replacement_endpoint_ids: set[str] = set()
    for doc_id, prior in previous_by_id.items():
        record = retired.get(doc_id)
        if record is None or record.get("retire_reason") != "replaced":
            continue
        replacement_id = str(record.get("replaced_by_id")) if record.get("replaced_by_id") else None
        if replacement_id is None:
            continue
        endpoint_id = _chain_ends_on_active(replacement_id, retired, active_ids)
        if endpoint_id is None:
            continue
        replacement = active_by_id.get(endpoint_id)
        if replacement is None:
            continue
        replaced.append(
            {
                "old_name": prior["name"],
                "new_name": replacement["name"],
            }
        )
        replacement_endpoint_ids.add(endpoint_id)

    # Active documents absent from the previous snapshot are `added`,
    # except those that are the endpoint of a reported replacement chain.
    added = [
        {"name": item["name"]}
        for item in current_active
        if str(item["document_id"]) not in previous_by_id
        and str(item["document_id"]) not in replacement_endpoint_ids
    ]

    # Previous documents that are still active are unchanged; those that are
    # retired and not part of a successful replacement are `removed`.
    removed = []
    for doc_id, prior in previous_by_id.items():
        if doc_id in active_ids:
            continue
        record = retired.get(doc_id)
        if record is not None and record.get("retire_reason") == "replaced":
            replacement_id = str(record.get("replaced_by_id")) if record.get("replaced_by_id") else None
            if replacement_id is not None and _chain_ends_on_active(replacement_id, retired, active_ids) is not None:
                continue
        removed.append({"name": prior["name"]})

    return {
        "added": added,
        "removed": removed,
        "replaced": replaced,
    }


def _is_replacement_endpoint(document_id: str, retired: dict) -> bool:
    """True when some retired document's ``replaced_by_id`` points at this id."""
    return any(
        str(record.get("replaced_by_id")) == document_id
        for record in retired.values()
        if record.get("replaced_by_id") is not None
    )