"""Approval finalisation service (Unit 23).

``finalise_approved_application`` is the one place that turns a finally-approved
application into (1) the annual-leave balance deduction and (2) the official
approved-leave PDF stored through the Unit 19 storage backend. It runs as the
finalise step after the approval decision commits (``workflows.events`` routes
the ``application_finalised`` event here) and keeps every database write in one
transaction: a failure rolls back the ledger row and document row together so
the application is never left half-processed.
"""

import logging
import os
import uuid

from audit.services import record_event
from django.db import transaction
from django.utils import timezone

from leave.cancellations.services import get_balance_provider
from leave.models import LeaveApplication
from leave.storage import get_storage_backend

from .generator import generate_approved_document
from .models import ApprovedLeaveDocument

logger = logging.getLogger(__name__)

CONTENT_TYPE_PDF = "application/pdf"

ACTION_BALANCE_DEDUCTED = "balance.deducted"
ACTION_DOCUMENT_GENERATED = "approved_document.generated"


def finalise_approved_application(application_id) -> ApprovedLeaveDocument | None:
    """Deduct the approved days and (re)generate the approved-leave PDF.

    Returns the :class:`ApprovedLeaveDocument` row, or ``None`` when the
    application no longer exists or is not approved. Idempotent: a repeated
    call replaces the stored PDF and refreshes the row (one per application)
    and never duplicates the ledger deduction.
    """
    application = (
        LeaveApplication.objects.select_related(
            "employee", "employee__employee_profile"
        )
        .filter(pk=application_id)
        .first()
    )
    if application is None or application.status != LeaveApplication.Status.APPROVED:
        return None

    stored_path = None
    try:
        with transaction.atomic():
            deduction = get_balance_provider().record_deduction(application)
            if deduction is not None:
                record_event(
                    actor=None,
                    action=ACTION_BALANCE_DEDUCTED,
                    target=application,
                    prev_state="pending",
                    new_state=application.status,
                    metadata={
                        "balance_transaction_id": str(deduction.id),
                        "days": str(deduction.days),
                        "financial_year": deduction.financial_year,
                    },
                )

            bytes_payload = generate_approved_document(application)

            document_id = uuid.uuid4()
            file_name = _file_name(application)
            path = (
                f"approved-leave-documents/{application.id}/"
                f"{document_id}/{file_name}"
            )
            get_storage_backend().put(
                path=path, file_obj=bytes_payload, content_type=CONTENT_TYPE_PDF
            )
            stored_path = path

            previous = ApprovedLeaveDocument.objects.filter(
                application=application
            ).first()
            if previous is not None:
                existing = previous.file_path
                previous.file_path = path
                previous.file_name = file_name
                previous.file_size = len(bytes_payload)
                previous.content_type = CONTENT_TYPE_PDF
                previous.save(
                    update_fields=["file_path", "file_name", "file_size", "content_type"]
                )
                document = previous
                if existing != path:
                    _remove_stored_file_best_effort(existing)
            else:
                document = ApprovedLeaveDocument.objects.create(
                    application=application,
                    file_path=path,
                    file_name=file_name,
                    file_size=len(bytes_payload),
                    content_type=CONTENT_TYPE_PDF,
                )

            record_event(
                actor=None,
                action=ACTION_DOCUMENT_GENERATED,
                target=application,
                prev_state="pending",
                new_state=application.status,
                metadata={
                    "document_id": str(document.id),
                    "file_name": file_name,
                    "file_size": document.file_size,
                },
            )
            return document
    except Exception:
        if stored_path:
            _remove_stored_file_best_effort(stored_path)
        raise


def _file_name(application: LeaveApplication) -> str:
    reference = (application.reference_number or "approved-leave").strip().lower()
    safe = "".join(char if char.isalnum() else "-" for char in reference).strip("-")
    return f"{safe}.pdf"


def _remove_stored_file_best_effort(path: str) -> None:
    try:
        get_storage_backend().remove(path)
    except Exception:  # noqa: BLE001 - storage failures never block the row op
        logger.exception("Failed to remove superseded approved document %s", path)