"""Unit 23 tests: finalised annual balance deduction + approved-leave PDF.

Covers ``documents.finalisation`` and everything wired around it:

* the ledger ``DEDUCTION`` written on final approval, sized by the approved
  working days of the application and driven by the immutable rules snapshot
  (invariant 12.5);
* the generated ``ApprovedLeaveDocument`` row and its storage file;
* idempotency of repeated finalisation (single ledger row, replaced document);
* the balance read-surface (``get_leave_balance``) reflecting the deduction;
* the review-payload ``approved_document`` pointer block;
* the authorized streaming endpoint (owner / workflow member / HR only).

``APPROVAL_FINALISATION`` is ``"off"`` in the test settings so the rest of the
suite stays free of ledger rows and stored files; these tests turn it ``"on"``
explicitly and point ``LEAVE_STORAGE_ROOT`` at a throwaway directory.
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEvent
from leave.defaults import ensure_default_entitlements
from leave.models import LeaveApplication, LeaveBalanceTransaction
from leave.providers import get_provider
from leave.storage import get_storage_backend
from leave.tests.stubs import make_user
from users.models import EmployeeProfile
from workflows.policies import can_view_approved_document
from workflows.tests_approvals import ApprovalFixtureMixin

from .finalisation import finalise_approved_application
from .generator import _resolve_values, generate_approved_document
from .models import ApprovedLeaveDocument
from .services import FIELD_CATALOG, get_template

# Shared throwaway storage root so finalisation tests never write into the
# repository checkout. LEAVE_STORAGE_BACKEND stays the dev disk backend.
TEMP_STORAGE = Path(tempfile.mkdtemp(prefix="luanar-unit23-"))

FINALISE = override_settings(
    APPROVAL_FINALISATION="on",
    LEAVE_STORAGE_ROOT=TEMP_STORAGE,
)


def _make_approved_application(
    *,
    employee,
    leave_type_id=1,
    working_days=5,
    snapshot_deducts=True,
    reference=None,
):
    """A plain approved row shaped exactly like a finally-approved submission.

    Bypasses validation on purpose: finalisation only ever sees the application
    after the decision service has committed it.
    """
    return LeaveApplication.objects.create(
        employee=employee,
        leave_type_id=leave_type_id,
        start_date=date(2026, 9, 28),
        end_date=date(2026, 10, 2),
        working_days=working_days,
        calculated_days=working_days,
        financial_year_label="2026-27",
        reference_number=reference,
        reason="Annual leave",
        status=LeaveApplication.Status.APPROVED,
        rules_snapshot={"leave_type": {"deducts_annual_balance": snapshot_deducts}},
    )


@FINALISE
class PipelineFinalisationTests(ApprovalFixtureMixin, TransactionTestCase):
    """The real pipeline: final approve triggers the deduction + document."""

    def setUp(self):
        self.setUpApprovals()

    def test_final_approval_deducts_exactly_the_working_days(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        app.refresh_from_db()

        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        transaction = LeaveBalanceTransaction.objects.get(
            application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
        )
        self.assertEqual(transaction.days, Decimal(app.working_days))
        self.assertEqual(transaction.days, Decimal("5"))
        self.assertEqual(transaction.financial_year, app.financial_year_label)
        self.assertEqual(transaction.leave_type.name, "Annual Leave")
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(application=app).count(), 1
        )

        self.assertTrue(
            AuditEvent.objects.filter(
                action="balance.deducted", object_id=str(app.id)
            ).exists()
        )

    def test_final_approval_writes_the_approved_document(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)

        document = ApprovedLeaveDocument.objects.get(application=app)
        self.assertEqual(document.content_type, "application/pdf")
        self.assertTrue(document.file_name.endswith(".pdf"))
        self.assertGreater(document.file_size, 0)
        self.assertTrue(get_storage_backend().exists(document.file_path))

        stored = get_storage_backend().open(document.file_path).read()
        self.assertTrue(stored.startswith(b"%PDF"))

        self.assertTrue(
            AuditEvent.objects.filter(
                action="approved_document.generated", object_id=str(app.id)
            ).exists()
        )

    def test_review_payload_exposes_the_document_pointer(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)

        client = APIClient()
        client.force_authenticate(self.hod)
        response = client.get(f"/api/v1/approvals/{app.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        block = response.data.get("approved_document")
        self.assertIsNotNone(block)
        document = ApprovedLeaveDocument.objects.get(application=app)
        self.assertEqual(block["id"], str(document.id))
        self.assertTrue(
            block["content_url"].endswith(
                f"/api/v1/leave-applications/{app.id}/approved-document/"
            )
        )

    def test_review_payload_pointer_is_null_before_finalisation(self):
        app = self.submit()

        client = APIClient()
        client.force_authenticate(self.hod)
        response = client.get(f"/api/v1/approvals/{app.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data.get("approved_document"))
        self.assertFalse(
            ApprovedLeaveDocument.objects.filter(application=app).exists()
        )


class FinalisationServiceTests(TestCase):
    """Unit tests on the finalisation service itself (plain approved rows)."""

    def setUp(self):
        self.user = make_user()
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            designation="Lecturer",
            department="Computer Science",
            category="academic",
            grade="C",
            appointment_date=date(2020, 1, 1),
        )

    @override_settings(LEAVE_STORAGE_ROOT=TEMP_STORAGE)
    def test_snapshot_without_deduction_still_generates_document(self):
        ensure_default_entitlements()
        app = _make_approved_application(
            employee=self.user, snapshot_deducts=False
        )

        document = finalise_approved_application(app.id)

        self.assertIsNotNone(document)
        self.assertFalse(
            LeaveBalanceTransaction.objects.filter(application=app).exists()
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action="balance.deducted", object_id=str(app.id)
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="approved_document.generated", object_id=str(app.id)
            ).exists()
        )

    @override_settings(LEAVE_STORAGE_ROOT=TEMP_STORAGE)
    def test_repeat_finalisation_replaces_document_keeps_one_ledger_row(self):
        app = _make_approved_application(
            employee=self.user, reference="LMS-23-0001"
        )

        first = finalise_approved_application(app.id)
        first_path = first.file_path
        second = finalise_approved_application(app.id)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.file_name, "lms-23-0001.pdf")
        self.assertEqual(
            ApprovedLeaveDocument.objects.filter(application=app).count(), 1
        )
        self.assertEqual(
            LeaveBalanceTransaction.objects.filter(
                application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
            ).count(),
            1,
        )
        self.assertNotEqual(first_path, second.file_path)
        self.assertFalse(get_storage_backend().exists(first_path))
        self.assertTrue(get_storage_backend().exists(second.file_path))

    @override_settings(LEAVE_STORAGE_ROOT=TEMP_STORAGE)
    def test_not_approved_application_is_ignored(self):
        app = _make_approved_application(employee=self.user)
        app.status = LeaveApplication.Status.PENDING
        app.save(update_fields=["status"])

        self.assertIsNone(finalise_approved_application(app.id))
        self.assertFalse(
            LeaveBalanceTransaction.objects.filter(application=app).exists()
        )
        self.assertFalse(
            ApprovedLeaveDocument.objects.filter(application=app).exists()
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action="approved_document.generated", object_id=str(app.id)
            ).exists()
        )

    @override_settings(LEAVE_STORAGE_ROOT=TEMP_STORAGE)
    def test_ledger_balance_read_surface_reflects_the_deduction(self):
        ensure_default_entitlements()
        app = _make_approved_application(employee=self.user, working_days=5)

        finalise_approved_application(app.id)

        balance = get_provider().get_leave_balance(self.user.id, "2026-27")
        self.assertEqual(balance.entitlement, 21)
        self.assertEqual(balance.used, 5)
        self.assertEqual(balance.available, 16)


@FINALISE
class StreamingAccessTests(ApprovalFixtureMixin, TransactionTestCase):
    """can_view_approved_document and the streaming endpoint."""

    def setUp(self):
        self.setUpApprovals()
        self.auditor = make_user(username="unrelated@test.luanar")
        self.hr = make_user(username="hr@test.luanar", role="hr")
        self.client = APIClient()

    def test_authorisation_grid(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)

        self.assertTrue(can_view_approved_document(self.employee, app))
        self.assertTrue(can_view_approved_document(self.hod, app))
        self.assertTrue(can_view_approved_document(self.hr, app))
        self.assertFalse(can_view_approved_document(self.auditor, app))

    def test_owner_and_approver_and_hr_stream_the_pdf(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        url = f"/api/v1/leave-applications/{app.id}/approved-document/"

        for who in (self.employee, self.hod, self.hr):
            self.client.force_authenticate(who)
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response["Content-Type"], "application/pdf"
            )
            content = b"".join(response.streaming_content)
            self.assertTrue(content.startswith(b"%PDF"))

    def test_download_param_attaches_the_file(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)

        self.client.force_authenticate(self.employee)
        response = self.client.get(
            f"/api/v1/leave-applications/{app.id}/approved-document/?download=1"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_unrelated_user_gets_404(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)

        self.client.force_authenticate(self.auditor)
        response = self.client.get(
            f"/api/v1/leave-applications/{app.id}/approved-document/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_approved_application_without_document_gets_404(self):
        app = _make_approved_application(employee=self.employee)
        self.assertTrue(
            can_view_approved_document(self.employee, app)
        )

        self.client.force_authenticate(self.employee)
        response = self.client.get(
            f"/api/v1/leave-applications/{app.id}/approved-document/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GeneratorTests(TestCase):
    """The pure PDF renderer."""

    def setUp(self):
        self.user = make_user()
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            designation="Lecturer",
            department="Computer Science",
            category="academic",
            grade="C",
            appointment_date=date(2020, 1, 1),
        )

    def test_generates_well_formed_pdf_bytes(self):
        app = _make_approved_application(
            employee=self.user, reference="LMS-23-0001"
        )

        pdf = generate_approved_document(app)

        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 500)

    def test_renders_configured_field_catalog_values(self):
        app = _make_approved_application(
            employee=self.user,
            reference="LMS-23-0001",
            snapshot_deducts=False,
        )
        app.rules_snapshot = {
            "leave_type": {"name": "Emergency Leave", "deducts_annual_balance": False}
        }

        values = _resolve_values(app)

        self.assertEqual(values["reference"], "LMS-23-0001")
        self.assertEqual(values["employee_name"], self.user.username)
        self.assertEqual(values["employee_grade"], "C")
        self.assertEqual(values["designation"], "Lecturer")
        self.assertEqual(values["department"], "Computer Science")
        self.assertEqual(values["leave_type"], "Emergency Leave")
        self.assertEqual(values["start_date"], "2026-09-28")
        self.assertEqual(values["end_date"], "2026-10-02")
        self.assertEqual(values["working_days"], "5")
        self.assertEqual(values["request_reason"], "Annual leave")
        self.assertEqual(
            set(_resolve_values(app).keys()),
            {item["key"] for item in FIELD_CATALOG},
        )

    def test_template_is_loaded(self):
        self.assertIsNotNone(get_template())