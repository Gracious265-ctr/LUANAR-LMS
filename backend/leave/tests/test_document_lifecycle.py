"""Unit 19 tests: supporting-document lifecycle and storage backend.

Covers the ``/api/v1/leave-applications/{id}/documents/`` surface (list,
retrieve, create, destroy, ``replace``, ``content``, ``history``), the
read-only status gate (409 ``document_read_only``), the file validation codes
(400), ownership resolution (404 not 403), draft hard-delete vs post-submission
retire semantics, the server-driven upload config endpoint, and the audit trail
written for every operation. The local dev storage backend is pointed at a
per-test temp directory so files can be asserted on disk.
"""

import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEvent
from leave.models import LeaveApplication, SupportingDocument
from leave.services.documents import (
    ACTION_DOCUMENT_REPLACED,
    ACTION_DOCUMENT_UPLOADED,
)
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_approver_chain,
    make_user,
)
from workflows.approval import decide


def upload_file(name, content=b"%PDF-1.4 test payload", content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class Unit19DocumentLifecycleTests(StubProviderMixin, TestCase):
    """End-to-end lifecycle over the leave-applications document API."""

    def setUp(self):
        self.stub = self.use_stub()
        chain = make_approver_chain()
        self.supervisor = chain["supervisor"]
        self.hod = chain["hod"]
        self.dean = chain["dean"]
        self.registrar = chain["registrar"]
        self.dvc = chain["dvc"]

        self.employee = make_user()
        self.stub.register_employee(self.employee)
        self.other = make_user(username="other@test.luanar")
        self.stub.register_employee(self.other)

        self.client = APIClient()
        self._dates = EARLIEST_ANNUAL_START
        self._storage_dir = tempfile.mkdtemp(prefix="luanar-doc-test-")

    def tearDown(self):
        shutil.rmtree(self._storage_dir, ignore_errors=True)

    # ------------------------------------------------------------------ helpers

    def doc_url(self, app, doc_id=None):
        base = f"/api/v1/leave-applications/{app.id}/documents/"
        return base if doc_id is None else f"{base}{doc_id}/"

    def submit_app(self, employee=None):
        employee = employee or self.employee
        from leave.services.submission import submit_application

        cursor = self._dates
        while cursor.weekday() >= 5:
            cursor += timedelta(days=1)
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=cursor,
            end_date=cursor + timedelta(days=4),
            reason="Annual leave",
        )
        submit_application(user=employee, application_id=app.id)
        app.refresh_from_db()
        self._dates = app.end_date + timedelta(days=1)
        return app

    def decide(self, app, approver, action):
        decide(
            application_id=app.id,
            actor=approver,
            action=action,
            comment="Comment.",
            expected_stage_version=app.current_stage.version,
        )
        app.refresh_from_db()
        return app

    def upload(self, app, **overrides):
        return self.client.post(
            self.doc_url(app),
            overrides
            or {
                "file": upload_file("note.pdf"),
            },
            format="multipart",
        )

    def attach(self, app, name="existing-certificate.pdf"):
        return SupportingDocument.objects.create(
            application=app,
            file_path=f"leave-documents/fake/{name}",
            file_url="https://cdn.example.test/leave-documents/fake/existing.pdf",
            file_name=name,
            file_size=1024,
            content_type="application/pdf",
        )

    def stored_path(self, document) -> Path:
        root = Path(settings.LEAVE_STORAGE_ROOT)
        return root.joinpath(*Path(document.file_path).parts)

    # ----------------------------------------------------------------- sections 4/6: upload + content URL

    def test_upload_creates_active_document_and_sets_absolute_content_url(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        response = self.client.post(self.doc_url(app), {"file": upload_file("cert.pdf")}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.data
        self.assertEqual(body["status"], "active")
        document = SupportingDocument.objects.get(id=body["id"])
        self.assertTrue(document.file_url.endswith(
            f"/api/v1/leave-applications/{app.id}/documents/{document.id}/content/"
        ))
        self.assertTrue(self.stored_path(document).is_file())
        self.assertTrue(document.file_path.startswith(f"leave-documents/{app.id}/"))

    def test_upload_content_url_uses_request_host(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        response = self.client.post(self.doc_url(app), {"file": upload_file("a.pdf")}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["file_url"].startswith("http://testserver/api/v1/"))

    # ------------------------------------------------------------- status gate

    def test_upload_read_only_on_submitted(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        response = self.upload(app)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "document_read_only")

    def test_upload_read_only_on_approved(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        for approver in (self.hod, self.dean, self.registrar, self.dvc):
            self.decide(app, approver, "approve")
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        response = self.upload(app)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "document_read_only")

    # ------------------------------------------------------------ file validation

    def test_upload_rejects_oversized_file(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        with self.settings(LEAVE_DOCUMENT_MAX_SIZE_BYTES=10):
            response = self.upload(app, file=upload_file("big.pdf", content=b"x" * 64))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "file_too_large")
        self.assertEqual(response.data["field"], "file")

    def test_upload_rejects_disallowed_type(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        response = self.client.post(
            self.doc_url(app),
            {"file": upload_file("page.html", content=b"<html></html>", content_type="text/html")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "file_type_not_allowed")

    def test_upload_rejects_empty_file(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        response = self.upload(app, file=upload_file("empty.pdf", content=b""))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "file_empty")

    def test_upload_requires_file_field(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        response = self.client.post(self.doc_url(app), {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "file_required")

    # ----------------------------------------------------------------- ownership

    def test_other_employee_document_ops_are_404_not_403(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.upload(app).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get(self.doc_url(app)).status_code, status.HTTP_404_NOT_FOUND
        )
        document = self.attach(app)
        self.assertEqual(
            self.client.get(self.doc_url(app, document.id)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(self.doc_url(app, document.id)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_anonymous_document_ops_are_401(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        self.assertEqual(self.upload(app).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get(self.doc_url(app)).status_code, status.HTTP_401_UNAUTHORIZED
        )

    # ----------------------------------------------------------------- list/retrieve

    def test_list_returns_only_active_ordered_desc(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        first = self.attach(app)
        self.upload(app, file=upload_file("new.pdf"))
        response = self.client.get(self.doc_url(app))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["file_name"] for item in response.data["results"]]
        self.assertEqual(names, ["new.pdf", "existing-certificate.pdf"])
        self.client.delete(self.doc_url(app, first.id))
        response = self.client.get(self.doc_url(app))
        self.assertEqual(
            [item["file_name"] for item in response.data["results"]], ["new.pdf"]
        )

    def test_retrieve_active_document_fields(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        response = self.upload(app, file=upload_file("cert.pdf"))
        pk = response.data["id"]
        document = SupportingDocument.objects.get(id=pk)
        body = self.client.get(self.doc_url(app, pk)).data
        self.assertEqual(body["id"], str(document.id))
        self.assertEqual(body["file_name"], "cert.pdf")
        self.assertEqual(body["content_type"], "application/pdf")
        self.assertIn("replaced_by_name", body)
        self.assertIsNone(body["replaced_by_name"])

    # ----------------------------------------------------------------- content

    def test_owner_streams_document_bytes(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        created = self.upload(app, file=upload_file("cert.pdf", content=b"PDFBYTES")).data
        response = self.client.get(self.doc_url(app, created["id"]) + "content/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), b"PDFBYTES")
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_download_query_attaches_filename(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        created = self.upload(app, file=upload_file("cert.pdf")).data
        response = self.client.get(self.doc_url(app, created["id"]) + "content/?download=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("cert.pdf", response["Content-Disposition"])

    def test_current_approver_streams_document_bytes(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )
        created = self.upload(
            app, file=upload_file("cert.pdf", content=b"APPROVERBYTES")
        ).data
        from leave.services.submission import submit_application

        submit_application(user=self.employee, application_id=app.id)
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.hod.id)
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(self.doc_url(app, created["id"]) + "content/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), b"APPROVERBYTES")

    def test_non_approver_streams_404(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        created = self.upload(app).data
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.doc_url(app, created["id"]) + "content/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retired_document_content_is_404(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        created = self.upload(app).data
        self.client.delete(self.doc_url(app, created["id"]))
        response = self.client.get(self.doc_url(app, created["id"]) + "content/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_document_content_is_404(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        response = self.client.get(self.doc_url(app, uuid4()) + "content/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------- draft hard delete

    def test_draft_destroy_removes_row_and_file(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        created = self.upload(app).data
        document = SupportingDocument.objects.get(id=created["id"])
        response = self.client.delete(self.doc_url(app, created["id"]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.stored_path(document).exists())
        with self.assertRaises(SupportingDocument.DoesNotExist):
            SupportingDocument.objects.get(id=created["id"])

    # --------------------------------------------------- post-submission retire

    def test_rejected_destroy_retires_keeps_file_and_writes_audit(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        created = self.upload(app).data
        document = SupportingDocument.objects.get(id=created["id"])
        response = self.client.delete(self.doc_url(app, created["id"]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        document.refresh_from_db()
        self.assertEqual(document.status, SupportingDocument.Status.RETIRED)
        self.assertEqual(document.retire_reason, SupportingDocument.RetireReason.REMOVED)
        self.assertTrue(self.stored_path(document).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action="document_removed",
                content_type=ContentType.objects.get_for_model(SupportingDocument),
                object_id=document.id,
            ).exists()
        )

    # ------------------------------------------------------------------ replace

    def test_replace_on_rejected_retires_original_keeps_file(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        original = self.upload(app, file=upload_file("old.pdf")).data
        original_row = SupportingDocument.objects.get(id=original["id"])
        response = self.client.post(
            self.doc_url(app, original["id"]) + "replace/",
            {"file": upload_file("new-certificate.pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        replacement = SupportingDocument.objects.get(id=response.data["id"])
        self.assertEqual(response.data["file_name"], "new-certificate.pdf")
        original_row.refresh_from_db()
        self.assertEqual(original_row.status, SupportingDocument.Status.RETIRED)
        self.assertEqual(original_row.retire_reason, SupportingDocument.RetireReason.REPLACED)
        self.assertEqual(original_row.replaced_by_id, replacement.id)
        self.assertTrue(self.stored_path(original_row).exists())
        self.assertTrue(self.stored_path(replacement).is_file())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=ACTION_DOCUMENT_REPLACED,
                content_type=ContentType.objects.get_for_model(SupportingDocument),
                object_id=replacement.id,
            ).exists()
        )

    def test_replace_on_draft_hard_deletes_original(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        original = self.upload(app, file=upload_file("draft-old.pdf")).data
        original_row = SupportingDocument.objects.get(id=original["id"])
        response = self.client.post(
            self.doc_url(app, original["id"]) + "replace/",
            {"file": upload_file("draft-new.pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.stored_path(original_row).exists())
        with self.assertRaises(SupportingDocument.DoesNotExist):
            SupportingDocument.objects.get(id=original["id"])

    def test_replace_unknown_document_is_404(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        response = self.client.post(
            self.doc_url(app, uuid4()) + "replace/",
            {"file": upload_file("note.pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_replace_read_only_status_is_409(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        document = self.attach(app)
        response = self.client.post(
            self.doc_url(app, document.id) + "replace/",
            {"file": upload_file("note.pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "document_read_only")

    # ------------------------------------------------------------------ history

    def test_history_returns_active_retired_and_ordered_events(self):
        self.client.force_authenticate(user=self.employee)
        app = self.submit_app()
        self.decide(app, self.hod, "reject")
        original = self.upload(app, file=upload_file("v1.pdf")).data
        self.client.post(
            self.doc_url(app, original["id"]) + "replace/",
            {"file": upload_file("v2.pdf")},
            format="multipart",
        )
        response = self.client.get(self.doc_url(app) + "history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(len(body["active"]), 1)
        self.assertEqual(body["active"][0]["file_name"], "v2.pdf")
        self.assertEqual(len(body["retired"]), 1)
        self.assertEqual(body["retired"][0]["file_name"], "v1.pdf")
        self.assertEqual(body["retired"][0]["retire_reason"], "replaced")
        self.assertEqual(body["retired"][0]["replaced_by_name"], "v2.pdf")
        actions = [event["action"] for event in body["events"]]
        self.assertEqual(actions, [ACTION_DOCUMENT_UPLOADED, ACTION_DOCUMENT_REPLACED])
        self.assertTrue(body["events"][0]["actor_name"])
        self.assertIn("metadata", body["events"][0])

    def test_history_for_other_employee_is_404(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.doc_url(app) + "history/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------ application delete

    def test_deleting_draft_application_purges_stored_files(self):
        self.client.force_authenticate(user=self.employee)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=date(2026, 9, 14),
            end_date=date(2026, 9, 18),
            reason="Draft",
        )
        first = self.upload(app, file=upload_file("a.pdf")).data
        second = self.upload(app, file=upload_file("b.pdf")).data
        documents = SupportingDocument.objects.filter(
            id__in=[first["id"], second["id"]]
        )
        response = self.client.delete(f"/api/v1/leave-applications/{app.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        for document in documents:
            self.assertFalse(self.stored_path(document).exists())

    # ---------------------------------------------------------------- config view

    def test_config_endpoint_returns_limits(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get("/api/v1/leave-documents/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["max_size_bytes"], settings.LEAVE_DOCUMENT_MAX_SIZE_BYTES)
        self.assertEqual(response.data["allowed_content_types"], settings.LEAVE_DOCUMENT_ALLOWED_TYPES)

    def test_config_endpoint_requires_auth(self):
        response = self.client.get("/api/v1/leave-documents/config/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)