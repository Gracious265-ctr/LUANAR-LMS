"""Newest-vs-previously-seen diffing for resubmissions (Unit 17).

The approval review payload shows an approver exactly what an employee changed
between the cycle this approver decided in and the current resubmission. Two
snapshots are diffed purely (no DB access): the previous snapshot (the latest
revision the approver had seen, i.e. the cycle-1 baseline) and the current
snapshot (the live application). Authentication/authority is the caller's job;
this module answers only "what is different".
"""

from __future__ import annotations

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
    )