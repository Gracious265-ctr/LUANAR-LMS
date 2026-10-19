"""Document lifecycle commands (Unit 19).

One small command layer between the ``SupportingDocumentViewSet`` and the
storage adapter. It owns the editable-status gate, the draft (hard delete)
versus rejected (retire-only) split, atomic replacement, and the audit
entries written in the same transaction as every mutation.

File validation is centralized here so every write path (upload, remove,
replace) enforces the same size/type constraints and produces the same error
messages the client already parses.
"""

import logging

from django.db import transaction
from rest_framework.exceptions import ValidationError

from audit.models import AuditEntry
from audit.services import record_audit

from ..models import LeaveApplication, SupportingDocument
from ..services.storage import (
    MAX_DOCUMENT_SIZE,
    delete_document,
    is_allowed_document_content_type,
    upload_document,
)

logger = logging.getLogger(__name__)

EDITABLE_STATUSES = frozenset(
    {LeaveApplication.Status.DRAFT, LeaveApplication.Status.REJECTED}
)


class DocumentNotEditableError(Exception):
    """The application is not in an editable status (409 ``application_not_editable``)."""


class DocumentNotActiveError(Exception):
    """The document is already retired and has no mutation path (409 ``document_not_active``)."""


def ensure_editable(application) -> None:
    """Raise ``DocumentNotEditableError`` unless the application is editable.

    Editable statuses are exactly ``draft`` and ``rejected`` (a rejected
    applicant may rework and resubmit); this is the single source of "read-only
    while under review / after approval".
    """
    if application.status not in EDITABLE_STATUSES:
        raise DocumentNotEditableError()


def _validate_file(file) -> None:
    """Enforce the existing size/type/name constraints on any written file."""
    if not file:
        raise ValidationError("No file provided.")
    if file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            f"Files may not exceed {MAX_DOCUMENT_SIZE // (1024 * 1024)} MB."
        )
    content_type = file.content_type or "application/octet-stream"
    if not is_allowed_document_content_type(content_type):
        raise ValidationError("File type is not allowed.")
    return content_type


def upload(user, application, file) -> SupportingDocument:
    """Upload a new active document onto an editable application."""
    ensure_editable(application)
    content_type = _validate_file(file)

    result = upload_document(file, str(application.id))
    with transaction.atomic():
        document = SupportingDocument.objects.create(
            application=application,
            file_path=result["path"],
            file_url=result["url"],
            file_name=file.name,
            file_size=file.size,
            content_type=content_type,
        )
        record_audit(
            actor=user,
            action=AuditEntry.Action.DOCUMENT_ADDED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=application.id,
            target_summary=document.file_name,
            detail={"document_id": str(document.id), "file_name": document.file_name},
        )
    return document


def remove(user, application, document) -> None:
    """Remove a document from an editable application.

    A draft removal is destructive-by-nature: the row is hard-deleted and the
    storage object removed. A rejected removal retires the row (the storage
    object is kept so the previous submission's snapshot still resolves).
    """
    ensure_editable(application)
    if document.status != SupportingDocument.Status.ACTIVE:
        raise DocumentNotActiveError()

    with transaction.atomic():
        if application.status == LeaveApplication.Status.DRAFT:
            try:
                delete_document(document.file_path)
            except Exception:
                logger.exception(
                    "Failed to delete document %s from storage", document.id
                )
            document.delete()
            record_audit(
                actor=user,
                action=AuditEntry.Action.DOCUMENT_REMOVED,
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=application.id,
                target_summary=document.file_name,
                detail={"document_id": str(document.id), "file_name": document.file_name},
            )
        else:
            document.retire(user, reason=SupportingDocument.RetireReason.REMOVED)
            record_audit(
                actor=user,
                action=AuditEntry.Action.DOCUMENT_RETIRED,
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=application.id,
                target_summary=document.file_name,
                detail={
                    "document_id": str(document.id),
                    "file_name": document.file_name,
                    "retire_reason": SupportingDocument.RetireReason.REMOVED,
                },
            )


def replace(user, application, document, file) -> SupportingDocument:
    """Replace a document on a ``rejected`` application.

    Valid only when the application is editable and **not** a draft — a draft
    replaces via remove + upload. The new file is uploaded first, then the old
    row is retired (``replaced``) pointing at the new row, all in one
    transaction so a storage failure never leaves a dangling pair.
    """
    ensure_editable(application)
    if application.status != LeaveApplication.Status.REJECTED:
        raise DocumentNotEditableError()
    if document.status != SupportingDocument.Status.ACTIVE:
        raise DocumentNotActiveError()
    content_type = _validate_file(file)

    result = upload_document(file, str(application.id))
    with transaction.atomic():
        replacement = SupportingDocument.objects.create(
            application=application,
            file_path=result["path"],
            file_url=result["url"],
            file_name=file.name,
            file_size=file.size,
            content_type=content_type,
        )
        document.retire(
            user,
            reason=SupportingDocument.RetireReason.REPLACED,
            replaced_by=replacement,
        )
        record_audit(
            actor=user,
            action=AuditEntry.Action.DOCUMENT_REPLACED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=application.id,
            target_summary=document.file_name,
            detail={
                "document_id": str(document.id),
                "file_name": document.file_name,
                "replaced_by": str(replacement.id),
                "replacement_name": replacement.file_name,
            },
        )
    return replacement