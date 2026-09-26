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
from django.db import models

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
    elif before is not None and after is None:
        metadata["before"] = _jsonable(before)
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


# Action -> (kind, human label, whether to append "by <actor>").
# Every action here can appear on a per-application timeline; delegation
# events (target = the delegation row) are deliberately absent.
TIMELINE_ACTIONS: dict[str, tuple[str, str, bool]] = {
    "leave_application.submitted": ("submission", "Submitted for approval", False),
    "leave_application.workflow_assigned": (
        "workflow_assignment",
        "Assigned to approval workflow",
        False,
    ),
    "leave_application.approve": ("decision", "Approved", True),
    "leave_application.reject": ("decision", "Rejected", True),
    "leave_application.return_for_correction": (
        "decision",
        "Returned for correction",
        True,
    ),
    "leave_application.changes_saved": ("revision", "Changes saved", True),
    "application_resubmitted": ("revision", "Resubmitted for approval", True),
    "cancellation.withdrawn": ("cancellation", "Application withdrawn", True),
    "cancellation.requested": ("cancellation", "Cancellation requested", True),
    "cancellation.stage_approved": (
        "cancellation",
        "Cancellation stage approved",
        True,
    ),
    "cancellation.approved": ("cancellation", "Cancellation approved", True),
    "cancellation.rejected": ("cancellation", "Cancellation rejected", True),
    "balance.restored": ("cancellation", "Leave days restored to balance", False),
    "application.reassigned": ("reassignment", "Reassigned", True),
    "balance.deducted": ("finalisation", "Approved days deducted from balance", False),
    "approved_document.generated": (
        "finalisation",
        "Approved leave document generated",
        False,
    ),
    "document_uploaded": ("document", "Supporting document uploaded", False),
    "document_removed": ("document", "Supporting document removed", False),
    "document_replaced": ("document", "Supporting document replaced", False),
}


def _actor_display(actor) -> str:
    if actor is None:
        return ""
    return actor.get_full_name() or actor.username


def _iso(value) -> str | None:
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _timeline_summary(action: str, metadata: dict) -> str:
    """A short action-specific explanation for the timeline entry."""
    if action == "application.reassigned":
        before = (metadata.get("before") or {}).get("current_approver")
        after = (metadata.get("after") or {}).get("current_approver")
        if before and after:
            return f"From {before} to {after}"
        if after:
            return f"Reassigned to {after}"
    if action in ("leave_application.approve", "leave_application.reject",
                  "leave_application.return_for_correction"):
        return str(metadata.get("reason", ""))
    if action == "document_replaced":
        return (
            f"{metadata.get('old_document_name', '')} "
            f"\u2192 {metadata.get('new_document_name', '')}".strip()
        )
    if action in ("document_uploaded", "document_removed"):
        return str(metadata.get("file_name", ""))
    return ""


def _render_timeline_event(event: AuditEvent) -> dict:
    """One display-ready timeline entry derived entirely from an event row."""
    kind, label, with_actor = TIMELINE_ACTIONS.get(
        event.action, ("audit", event.action.replace("_", " ").capitalize(), True)
    )
    actor = event.actor
    if with_actor and actor is not None:
        action_label = f"{label} by {_actor_display(actor)}"
    else:
        action_label = label

    metadata = event.metadata or {}
    return {
        "id": str(event.pk),
        "kind": kind,
        "action": event.action,
        "action_label": action_label,
        "occurred_at": _iso(event.created_at),
        "actor": {"id": actor.pk if actor else None, "name": _actor_display(actor)},
        "target_type": event.content_type.model if event.content_type else "",
        "state_transition": {
            "from": event.prev_state,
            "to": event.new_state,
        },
        "summary": _timeline_summary(event.action, metadata),
        "metadata": metadata,
        "stage_order": metadata.get("stage_order"),
        "resubmission_number": metadata.get("submission_cycle"),
    }


def application_timeline(application) -> list[dict]:
    """The chronological, reconstructable timeline for ``application``.

    Rows come only from the append-only :class:`AuditEvent` trail whose targets
    are the application itself or a row that belongs to it (supporting
    documents, cancellation requests, content revisions), so the trail survives
    any later object deletion. Entries are rendered oldest first through the
    ``kind`` / ``action_label`` lookup above; delegation events never appear
    here because they are person-to-person rather than application-scoped.
    """
    # Imported lazily so the audit package never becomes a hard dependency of
    # the leave/workflows models at import time.
    from leave.models import (
        ApplicationRevision,
        CancellationRequest,
        LeaveApplication,
        SupportingDocument,
    )

    conditions = models.Q(
        content_type=ContentType.objects.get_for_model(LeaveApplication),
        object_id=str(application.pk),
    )
    for model, ids in (
        (SupportingDocument, application.documents.values_list("id", flat=True)),
        (
            CancellationRequest,
            application.cancellation_requests.values_list("id", flat=True),
        ),
        (ApplicationRevision, application.revisions.values_list("id", flat=True)),
    ):
        ids = [str(pk) for pk in ids]
        if ids:
            conditions |= models.Q(
                content_type=ContentType.objects.get_for_model(model),
                object_id__in=ids,
            )

    events = (
        AuditEvent.objects.filter(conditions)
        .select_related("actor", "content_type")
        .order_by("created_at", "id")
    )
    return [_render_timeline_event(event) for event in events]
