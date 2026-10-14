<<<<<<< HEAD
"""Diff engine for resubmission change summaries (Unit 17, section 4).

``compute_changes`` is a pure, dependency-free function: given the content
snapshot of the previous revision and the application's current content, it
returns the ``Changes`` JSON shape the spec defines. It is used both when a
revision is created (at submit/resubmit) and for the live ``changes_preview``
on the edit page, so the preview always matches what the approver will see.
=======
"""Newest-vs-previously-seen diffing for resubmissions (Unit 17).

The approval review payload shows an approver exactly what an employee changed
between the cycle this approver decided in and the current resubmission. Two
snapshots are diffed purely (no DB access): the previous snapshot (the latest
revision the approver had seen, i.e. the cycle-1 baseline) and the current
snapshot (the live application). Authentication/authority is the caller's job;
this module answers only "what is different".
>>>>>>> feature/plans-teams
"""

from __future__ import annotations

<<<<<<< HEAD
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
=======
from dataclasses import dataclass
from datetime import date
from uuid import UUID

#: Human-readable labels for the diffable basic-shape fields.
FIELD_LABELS = {
    "leave_type": "Leave type",
    "start_date": "Start date",
    "end_date": "End date",
    "working_days": "Working days",
    "reason": "Reason",
}

#: Fields the diff engine compares. Documents are handled by the ``documents``
#: block, sizes and content types are deliberately not compared.
DIFFABLE_FIELDS = ("leave_type", "start_date", "end_date", "working_days", "reason")


@dataclass(frozen=True)
class FieldChange:
    """One changed basic-shape field."""

    label: str
    old_value: str
    new_value: str


@dataclass(frozen=True)
class DocumentChange:
    """One added/replaced/removed supporting document."""

    document_id: UUID
    name: str
    previous_document_id: UUID | None = None
    previous_name: str | None = None


@dataclass(frozen=True)
class Changes:
    """Everything that changed between two snapshots."""

    fields: list[FieldChange]
    documents_added: list[DocumentChange]
    documents_replaced: list[DocumentChange]
    documents_removed: list[DocumentChange]

    def to_payload(self) -> dict:
        """Serialise to the JSON shape stored on revisions and API responses."""
        return {
            "fields": [
                {"label": change.label, "old_value": change.old_value, "new_value": change.new_value}
                for change in self.fields
            ],
            "documents_added": [
                {"name": change.name, "document_id": str(change.document_id)}
                for change in self.documents_added
            ],
            "documents_replaced": [
                {
                    "name": change.name,
                    "document_id": str(change.document_id),
                    "previous_name": change.previous_name,
                    "previous_document_id": str(change.previous_document_id),
                }
                for change in self.documents_replaced
            ],
            "documents_removed": [
                {"name": change.name, "document_id": str(change.document_id)}
                for change in self.documents_removed
            ],
        }

    def is_empty(self) -> bool:
        return not (
            self.fields
            or self.documents_added
            or self.documents_replaced
            or self.documents_removed
        )


def _as_text(key: str, value) -> str:
    """Render a snapshot value for display (dates to ISO, days as integers)."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def compute_changes(
    previous_snapshot: dict | None, current_snapshot: dict | None
) -> Changes:
    """Return the changes ``current`` introduces over ``previous``.

    ``previous_snapshot`` may be ``None`` (no baseline seen yet) - everything
    present is treated as added/changed. ``current_snapshot`` documents carry
    ``replaces: [previous document ids]`` so this function stays free of the
    database: the caller resolves the active ``replaced_by`` chain into that
    list before calling. Rules:

    * Basic-shape fields are diffed when their values differ.
    * ``added`` = a current document not present in previous and not a
      replacement end (no ``replaces``).
    * ``replaced`` = one row per current ``replaces`` id.
    * ``removed`` = a previous document absent from current and not replaced.
    """
    previous = previous_snapshot or {}
    current = current_snapshot or {}

    prev_docs = {str(doc.get("document_id")): doc for doc in previous.get("documents") or []}
    current_docs = {str(doc.get("document_id")): doc for doc in current.get("documents") or []}

    field_changes: list[FieldChange] = []
    for key in DIFFABLE_FIELDS:
        old_value = _as_text(key, previous.get(key))
        new_value = _as_text(key, current.get(key))
        if old_value != new_value:
            field_changes.append(
                FieldChange(
                    label=FIELD_LABELS[key],
                    old_value=old_value,
                    new_value=new_value,
                )
            )

    added: list[DocumentChange] = []
    replaced: list[DocumentChange] = []
    removed: list[DocumentChange] = []
    replaced_ids: set[str] = set()

    for doc_id, doc in sorted(current_docs.items(), key=lambda item: item[1].get("name") or ""):
        name = doc.get("name") or ""
        if doc_id not in prev_docs and not doc.get("replaces"):
            added.append(DocumentChange(document_id=doc_id, name=name))
            continue
        for previous_id in doc.get("replaces") or []:
            previous_id = str(previous_id)
            replaced_ids.add(previous_id)
            previous_doc = prev_docs.get(previous_id, {})
            replaced.append(
                DocumentChange(
                    document_id=doc_id,
                    name=name,
                    previous_document_id=previous_id,
                    previous_name=previous_doc.get("name") or "",
                )
            )

    for doc_id, doc in sorted(prev_docs.items(), key=lambda item: item[1].get("name") or ""):
        if doc_id not in current_docs and doc_id not in replaced_ids:
            removed.append(
                DocumentChange(
                    document_id=doc_id,
                    name=doc.get("name") or "",
                )
            )

    return Changes(
        fields=field_changes,
        documents_added=added,
        documents_replaced=replaced,
        documents_removed=removed,
>>>>>>> feature/plans-teams
    )