"""Supporting-document lifecycle service (Unit 19).

Single authoritative module for every supporting-document operation: upload,
view/download, replace, remove (retire), history, and the read-only/enabled
status gate. Functions resolve the application through the owner check
``application.employee == actor`` (anything else -> 404, never 403; project
convention), take the actor from the authenticated user only, and run in
``transaction.atomic()``.

Status gate (see the Unit 19 spec section "Status gate"): editing is allowed in
``draft``, ``rejected`` and ``correction_required``; everything else rejects
mutation with a 409 ``document_read_only``. During ``draft`` a replace/remove
physically deletes the old file and row (Unit 13 behavior); from submission
onward the old row is retired and the file kept (Unit 17 rule).
"""

import logging
import os
import uuid

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from audit.services import record_event

from ..models import LeaveApplication, SupportingDocument
from ..serializers import SupportingDocumentSerializer
from ..storage import get_storage_backend

logger = logging.getLogger(__name__)

EDITABLE_STATUSES = (
    LeaveApplication.Status.DRAFT,
    LeaveApplication.Status.REJECTED,
    LeaveApplication.Status.CORRECTION_REQUIRED,
)

ACTION_DOCUMENT_UPLOADED = "document_uploaded"
ACTION_DOCUMENT_REMOVED = "document_removed"
ACTION_DOCUMENT_REPLACED = "document_replaced"


class ApplicationNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class DocumentNotFoundError(Exception):
    """The document is not part of this application or is no longer active."""


class DocumentError(Exception):
    """A document mutation was rejected; carries ``field``/``code``/``message``.

    ``code == "document_read_only"`` is mapped to 409; the ``file_*`` codes are
    mapped to 400 (see ``validate_upload_file``).
    """

    def __init__(self, *, field: str, code: str, message: str):
        self.field = field
        self.code = code
        self.message = message
        super().__init__(message)


def document_path(application_id, document_id, file_name: str) -> str:
    """Return the per-document storage path; the name is basename-normalised."""
    return (
        f"leave-documents/{application_id}/{document_id}/"
        f"{os.path.basename(file_name)}"
    )


def editing_allowed(application) -> bool:
    """Return True when mutations are allowed for ``application.status``.

    Raises ``DocumentError`` (409 ``document_read_only``) otherwise.
    """
    if application.status not in EDITABLE_STATUSES:
        raise DocumentError(
            field="status",
            code="document_read_only",
            message=(
                "Documents on this application are read-only in its current "
                "state."
            ),
        )
    return True


def validate_upload_file(file) -> None:
    """Enforce the server-authoritative upload limits (raising 400 codes)."""
    if file is None:
        raise DocumentError(
            field="file",
            code="file_required",
            message="Choose a file to upload.",
        )
    name = (file.name or "").strip()
    if not name:
        raise DocumentError(
            field="file",
            code="file_required",
            message="Choose a file to upload.",
        )
    if getattr(file, "size", None) == 0:
        raise DocumentError(
            field="file",
            code="file_empty",
            message="The selected file is empty.",
        )
    if file.size > settings.LEAVE_DOCUMENT_MAX_SIZE_BYTES:
        raise DocumentError(
            field="file",
            code="file_too_large",
            message=(
                f"The selected file exceeds the "
                f"{settings.LEAVE_DOCUMENT_MAX_SIZE_BYTES}-byte limit."
            ),
        )
    if file.content_type not in settings.LEAVE_DOCUMENT_ALLOWED_TYPES:
        raise DocumentError(
            field="file",
            code="file_type_not_allowed",
            message="This file type is not allowed.",
        )


def can_view_content(user, application) -> bool:
    """Return True when ``user`` may stream this application's documents.

    True for the owner, and for the current assigned approver (the Unit 9
    spine). Documented seam: Units 16/17 add approver ``get_view_access``
    calls here.
    """
    if application.employee_id == user.id:
        return True
    if application.current_approver_id == user.id:
        return True
    return False


def content_url(application_id, document_id, download: bool = False) -> str:
    """Return the relative content-endpoint path for a document."""
    base = (
        f"/api/v1/leave-applications/{application_id}/documents/"
        f"{document_id}/content/"
    )
    return base + ("?download=1" if download else "")


def set_content_url(document, request) -> None:
    """Set ``file_url`` to the absolute content-endpoint URL (section 6)."""
    document.file_url = request.build_absolute_uri(
        content_url(document.application_id, document.id)
    )
    document.save(update_fields=["file_url"])


def add_document(*, application_id, actor, file) -> SupportingDocument:
    """Gate, validate, upload and attach a new active document."""
    with transaction.atomic():
        application = _owned_application_or_404(application_id, actor)
        editing_allowed(application)
        validate_upload_file(file)

        document_id = uuid.uuid4()
        path = document_path(application.id, document_id, file.name)
        content_type = file.content_type or "application/octet-stream"
        get_storage_backend().put(
            path=path, file_obj=file, content_type=content_type
        )

        document = SupportingDocument.objects.create(
            application=application,
            file_path=path,
            file_url="",
            file_name=file.name.strip(),
            file_size=file.size,
            content_type=content_type,
            status=SupportingDocument.Status.ACTIVE,
        )

        record_event(
            actor=actor,
            action=ACTION_DOCUMENT_UPLOADED,
            target=document,
            prev_state=application.status,
            new_state=application.status,
            metadata={
                "application_id": str(application.id),
                "file_name": document.file_name,
            },
        )
        return document


def remove_document(*, application_id, document_id, actor) -> None:
    """Delete (draft) or retire (post-submission) ``document_id``."""
    with transaction.atomic():
        application = _owned_application_or_404(application_id, actor)
        editing_allowed(application)
        document = _active_document_or_404(application, document_id)

        # The audit event is written before the row is deleted/retired: the
        # draft path calls ``document.delete()`` which nulls ``pk`` on the
        # in-memory object, and recording after it would store ``object_id``
        # as ``None`` and orphan the event from the application trail.
        record_event(
            actor=actor,
            action=ACTION_DOCUMENT_REMOVED,
            target=document,
            prev_state=application.status,
            new_state=application.status,
            metadata={
                "application_id": str(application.id),
                "file_name": document.file_name,
            },
        )

        if application.status == LeaveApplication.Status.DRAFT:
            _remove_stored_file_best_effort(document)
            document.delete()
        else:
            _retire(
                document=document,
                actor=actor,
                reason=SupportingDocument.RetireReason.REMOVED,
                replaced_by=None,
            )


def replace_document(*, application_id, document_id, actor, file) -> SupportingDocument:
    """Replace ``document_id`` with a new upload; returns the new row.

    Draft: the old file + row are deleted (Unit 13 behavior). Rejected /
    correction-required: the old row is retired (``replaced_by`` set) and the
    old file is kept (Unit 17 rule).
    """
    with transaction.atomic():
        application = _owned_application_or_404(application_id, actor)
        editing_allowed(application)
        validate_upload_file(file)
        previous = _active_document_or_404(application, document_id)

        new_id = uuid.uuid4()
        new_path = document_path(application.id, new_id, file.name)
        content_type = file.content_type or "application/octet-stream"
        get_storage_backend().put(
            path=new_path, file_obj=file, content_type=content_type
        )

        replacement = SupportingDocument.objects.create(
            application=application,
            file_path=new_path,
            file_url="",
            file_name=file.name.strip(),
            file_size=file.size,
            content_type=content_type,
            status=SupportingDocument.Status.ACTIVE,
        )

        if application.status == LeaveApplication.Status.DRAFT:
            _remove_stored_file_best_effort(previous)
            previous.delete()
        else:
            _retire(
                document=previous,
                actor=actor,
                reason=SupportingDocument.RetireReason.REPLACED,
                replaced_by=replacement,
            )

        record_event(
            actor=actor,
            action=ACTION_DOCUMENT_REPLACED,
            target=replacement,
            prev_state=application.status,
            new_state=application.status,
            metadata={
                "application_id": str(application.id),
                "old_document_id": str(previous.id),
                "old_document_name": previous.file_name,
                "new_document_name": replacement.file_name,
            },
        )
        return replacement


def get_documents(application_id, actor, *, include_retired: bool = False) -> list:
    """Return the application's documents (active-only unless requested)."""
    application = _owned_application_or_404(application_id, actor)
    queryset = SupportingDocument.objects.filter(application_id=application.id)
    if not include_retired:
        queryset = queryset.filter(status=SupportingDocument.Status.ACTIVE)
    return list(queryset.order_by("-uploaded_at", "id"))


def get_document_history(application_id, actor) -> dict:
    """Compose ``{active, retired, events}`` for the application."""
    application = _owned_application_or_404(application_id, actor)

    active = list(
        application.documents.filter(status=SupportingDocument.Status.ACTIVE)
        .order_by("-uploaded_at", "id")
    )
    retired = list(
        application.documents.filter(status=SupportingDocument.Status.RETIRED)
        .select_related("replaced_by")
        .order_by("-retired_at", "id")
    )

    document_ids = [document.id for document in active] + [
        document.id for document in retired
    ]
    events = list(
        AuditEvent.objects.filter(
            content_type=ContentType.objects.get_for_model(SupportingDocument),
            object_id__in=document_ids,
            action__in=(
                ACTION_DOCUMENT_UPLOADED,
                ACTION_DOCUMENT_REMOVED,
                ACTION_DOCUMENT_REPLACED,
            ),
        )
        .select_related("actor")
        .order_by("created_at", "id")
    )

    return {
        "active": SupportingDocumentSerializer(active, many=True).data,
        "retired": SupportingDocumentSerializer(retired, many=True).data,
        "events": [
            {
                "id": str(event.id),
                "action": event.action,
                "actor_name": (
                    event.actor.get_full_name() or event.actor.username
                    if event.actor
                    else ""
                ),
                "occurred_at": _iso(event.created_at),
                "metadata": event.metadata,
            }
            for event in events
        ],
    }


def delete_draft_documents(application) -> None:
    """Best-effort remove every document's stored file (no row deletes).

    Called from ``LeaveApplicationViewSet.perform_destroy`` before the caller
    deletes the application (which cascades to the document rows).
    """
    for document in application.documents.all():
        _remove_stored_file_best_effort(document)


def get_document_content(document):
    """Return ``(open_file, content_type, file_name)`` for streaming."""
    return (
        get_storage_backend().open(document.file_path),
        document.content_type,
        document.file_name,
    )


def active_documents_queryset(application_id):
    """Shared only-active helper (retired documents never leak into lists)."""
    return SupportingDocument.objects.filter(
        application_id=application_id,
        status=SupportingDocument.Status.ACTIVE,
    )


def _owned_application_or_404(application_id, actor) -> LeaveApplication:
    application = (
        LeaveApplication.objects.select_for_update()
        .filter(id=application_id, employee=actor)
        .first()
    )
    if application is None:
        raise ApplicationNotFoundError()
    return application


def _active_document_or_404(application, document_id) -> SupportingDocument:
    document = application.documents.filter(
        id=document_id,
        status=SupportingDocument.Status.ACTIVE,
    ).first()
    if document is None:
        raise DocumentNotFoundError()
    return document


def _retire(*, document, actor, reason, replaced_by) -> None:
    document.status = SupportingDocument.Status.RETIRED
    document.retired_at = timezone.now()
    document.retired_by = actor
    document.retire_reason = reason
    document.replaced_by = replaced_by
    document.save(
        update_fields=[
            "status",
            "retired_at",
            "retired_by",
            "retire_reason",
            "replaced_by",
        ]
    )


def _remove_stored_file_best_effort(document) -> None:
    try:
        get_storage_backend().remove(document.file_path)
    except Exception:  # noqa: BLE001 - storage failures never block the row op
        logger.exception("Failed to delete document %s from storage", document.id)


def _iso(value) -> str:
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")