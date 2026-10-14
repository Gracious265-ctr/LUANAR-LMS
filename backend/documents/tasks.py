"""Background rendering of approved-leave documents (Unit 23b D5).

Dispatch via: ``async_task("documents.tasks.render_approved_document", document_id)``
— in practice enqueued by
:func:`documents.services.enqueue_approved_document_render` on commit, so the
render only starts once the approval transaction (and its balance deduction) is
durable.

A render failure is recorded on the row and logged in full server-side, but it
never propagates to the approval: the balance is transactional business state,
the document is a retryable derived artifact.
"""

import logging

from django.utils import timezone

from audit.models import AuditEntry
from audit.services import record_audit
from leave.services.storage import APPROVED_DOCUMENT_PREFIX, upload_bytes

from .models import ApprovedLeaveDocument
from .services import (
    APPROVED_DOCUMENT_CONTENT_TYPE,
    APPROVED_DOCUMENT_FILENAME,
    render_approved_document_pdf,
)

logger = logging.getLogger(__name__)


def render_approved_document(document_id) -> str:
    """Render and store one approved document; idempotent (D5).

    A row already ``ready`` is a no-op, so re-running the task (a Q2 retry, or
    re-finalising the application) can never regenerate or overwrite the
    artifact of what was approved. Returns the resulting status.
    """
    document = ApprovedLeaveDocument.objects.select_related("application").get(
        pk=document_id
    )
    if document.status == ApprovedLeaveDocument.Status.READY:
        return document.status

    application = document.application
    try:
        pdf_bytes = render_approved_document_pdf(application)
        if not pdf_bytes:
            raise ValueError("The renderer produced an empty document.")
        stored = upload_bytes(
            pdf_bytes,
            APPROVED_DOCUMENT_FILENAME,
            prefix=APPROVED_DOCUMENT_PREFIX,
            application_id=str(application.pk),
            content_type=APPROVED_DOCUMENT_CONTENT_TYPE,
        )
    except Exception as exc:
        logger.exception(
            "Approved-document render failed for application %s", application.pk
        )
        document.mark_failed(f"{type(exc).__name__}: {exc}")
        record_audit(
            actor=None,
            action=AuditEntry.Action.DOCUMENT_FAILED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=application.pk,
            target_summary=application.reference_number or "",
            detail={"document_id": str(document.pk), "status": document.status},
        )
        return document.status

    document.mark_ready(
        file_path=stored["path"],
        file_url=stored["url"],
        file_name=APPROVED_DOCUMENT_FILENAME,
        file_size=len(pdf_bytes),
        content_type=APPROVED_DOCUMENT_CONTENT_TYPE,
        approved_on=application.approved_on or timezone.now(),
        rendered_at=timezone.now(),
    )
    record_audit(
        actor=None,
        target_type=AuditEntry.TargetType.APPLICATION,
        action=AuditEntry.Action.DOCUMENT_GENERATED,
        target_id=application.pk,
        target_summary=application.reference_number or "",
        detail={
            "document_id": str(document.pk),
            "file_name": document.file_name,
            "file_size": document.file_size,
        },
    )
    return document.status
