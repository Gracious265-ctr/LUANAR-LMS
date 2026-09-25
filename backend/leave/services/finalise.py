"""Unit 23 — final approval, annual-balance deduction and approved document.

Finalisation is the single, idempotent close of an approved leave application:

* **D1 (annual-balance deduction)** — at most one append-only
  ``LeaveBalanceTransaction`` of type ``deduction`` exists per application.
  The decision is read from the application's persisted ``rules_snapshot``
  (D1 in the Unit 23 spec), exactly as Unit 18's restoration gate reads it,
  so approval and later cancellation agree on the same leave type.
* **D2 (approved document)** — an ``ApprovedLeaveDocument`` record is created
  (status ``pending``) and a render job is enqueued on commit; the finished
  PDF is stored under the ``approved/{application_id}/`` storage prefix and
  exposed through signed URLs only.

Append-only ledger guarantees: the writer uses ``get_or_create`` (identical to
Unit 18's restoration writer), and the partial unique constraint
``one_deduction_per_application`` guarantees exactly one deduction row.

This module is deliberately free of HTTP/auth — access control stays in the
view/dto seams (Unit 16 ``get_view_access``, Unit 19 document views). Only data
writes and render orchestration live here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet

from . import exceptions
from .exceptions import (
    ApplicationFinalisationError,
    DeductionAlreadyRecordedError,
    LeaveTypeNotResolvableError,
)

__all__ = [
    "DeductionAlreadyRecordedError",
    "LeaveTypeNotResolvableError",
    "ApplicationFinalisationError",
    "consume_deduction_decision",
    "record_deduction",
    "finalise_approved_application",
]


# ---------------------------------------------------------------------------
# D1 — annual-balance decision from the persisted snapshot
# ---------------------------------------------------------------------------


def consume_deduction_decision(application) -> bool:
    """Return whether the application's leave type consumes the annual balance.

    Read the decision from the persisted ``rules_snapshot`` (stable for the
    whole application lifecycle), mirroring Unit 18's cancellation gate so the
    two flows never disagree. Falls back to the fixture registry definitions
    from the submission snapshot when the snapshot entry is absent.
    """
    snapshot = getattr(application, "rules_snapshot", None) or {}
    leave_type = snapshot.get("leave_type") or {}
    if "deducts_annual_balance" in leave_type:
        return bool(leave_type["deducts_annual_balance"])

    submission = getattr(application, "submission_snapshot", None) or {}
    fixture = submission.get("leave_type") or {}
    if "deducts_annual_balance" in fixture:
        return bool(fixture["deducts_annual_balance"])

    raise LeaveTypeNotResolvableError(
        f"The annual-balance deduction decision for "
        f"application {application.reference_number} could not be resolved "
        f"from the submitted snapshot."
    )


# ---------------------------------------------------------------------------
# Append-only ledger write (exactly one deduction per application)
# ---------------------------------------------------------------------------


def record_deduction(application):
    """Append the annual-balance deduction row, exactly once per application.

    Uses ``get_or_create`` (the same append-only writer Unit 18 uses for
    restorations). The partial unique constraint (``application``,
    ``type='deduction'``) makes the write idempotent and race-safe.
    """
    from leave.cancellations.models import LeaveBalanceTransaction

    if not consume_deduction_decision(application):
        raise LeaveTypeNotResolvableError(
            f"Leave type does not deduct the annual balance; no ledger row."
        )

    days = application.working_days
    financial_year = application.financial_year_label
    if not days or days <= 0 or not financial_year:
        raise ApplicationFinalisationError(
            f"Application {application.reference_number} has no working days "
            f"or financial year; cannot record the deduction."
        )

    transaction, created = LeaveBalanceTransaction.objects.get_or_create(
        employee_id=application.employee_id,
        financial_year=financial_year,
        leave_type_id=application.leave_type_id,
        application=application,
        type=LeaveBalanceTransaction.Type.DEDUCTION,
        defaults={"days": days, "carry_forward_eligible": True},
    )
    return transaction


# ---------------------------------------------------------------------------
# Full finalisation orchestration
# ---------------------------------------------------------------------------


def finalise_approved_application(application) -> "QuerySet":
    """Finalise an approved application (D1 and D2), idempotent.

    Records the annual-balance deduction (D1) when the leave type consumes it,
    then creates the ``ApprovedLeaveDocument`` record (D2) with status
    ``pending`` and enqueues the render on commit. Safe to call repeatedly —
    every step is idempotent.
    """
    from documents.models import ApprovedLeaveDocument

    if consume_deduction_decision(application):
        record_deduction(application)

    document, created = ApprovedLeaveDocument.objects.get_or_create(
        application=application,
        defaults={"status": ApprovedLeaveDocument.Status.PENDING},
    )

    from documents.services import enqueue_approved_document_render

    enqueue_approved_document_render(document)
    return document
