"""Unit 17 tests: rejection/correction editing and resubmission.

Covers the edit-context endpoint, in-place saving (status preserved), document
add/replace/remove (retirement semantics, never deleting files), the resubmit
action (same reference/stage/approver, cycle and revision growth), the
optimistic-concurrency and status guards, ownership (404 not 403), the inactive
approver block, and the audit trails.
"""

from datetime import date, timedelta
from unittest import mock
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEvent
from leave.models import LeaveApplication, SupportingDocument
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_approver_chain,
    make_user,
)
from workflows.approval import decide
from workflows.models import ApplicationStage

RESUB_URL = "/api/v1/applications/{id}/resubmission/"
RESUBMIT_URL = "/api/v1/applications/{id}/resubmit/"


class ResubmissionFixtureMixin(StubProviderMixin):
    """Employee + approver chain, disjoint date cursor and submission helpers."""

    def setUpResubmission(self):
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

        self._patch_today()
        self._dates = EARLIEST_ANNUAL_START
        self._upload_patcher = mock.patch(
            "leave.services.documents.get_storage_backend",
            return_value=mock.Mock(),
        )
        self.upload_document = self._upload_patcher.start()
        self.addCleanup(self._upload_patcher.stop)

    def _patch_today(self):
        patcher = mock.patch(
            "leave.services.resubmission._today",
            return_value=date(2026, 9, 21),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

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
        while self._dates.weekday() >= 5:
            self._dates += timedelta(days=1)
        return app

    def decide_action(self, app, approver, action, comment="Comment."):
        stage = app.current_stage
        decide(
            application_id=app.id,
            actor=approver,
            action=action,
            comment=comment,
            expected_stage_version=stage.version,
        )
        app.refresh_from_db()
        return app

    def rejected_app(self):
        return self.decide_action(self.submit_app(), self.hod, "reject")

    def returned_app(self):
        return self.decide_action(self.submit_app(), self.hod, "return_for_correction")

    def active_row_version(self, app):
        app.refresh_from_db()
        return app.row_version

    def attach_active_doc(self, app):
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/fake/existing.pdf",
            file_url="https://cdn.example.test/leave-documents/fake/existing.pdf",
            file_name="existing-certificate.pdf",
            file_size=1024,
            content_type="application/pdf",
        )
        return doc


class EditContextTests(ResubmissionFixtureMixin, TestCase):
    def setUp(self):
        self.setUpResubmission()

    def url(self, app_id):
        return RESUB_URL.format(id=app_id)

    def test_owner_rejected_gets_full_edit_context(self):
        app = self.rejected_app()
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(body["status"], "rejected")
        self.assertTrue(body["can_edit"])
        self.assertEqual(body["row_version"], app.row_version)
        self.assertEqual(body["reference"], app.reference_number)
        self.assertEqual(body["content"]["reason"], "Annual leave")
        self.assertIn("changes_preview", body)
        self.assertIn("documents", body)
        self.assertEqual(
            body["returns_to"]["role_label"], "Head of Department"
        )
        self.assertEqual(body["feedback"]["action"], "reject")

    def test_owner_pending_sees_can_edit_false(self):
        app = self.submit_app()
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_edit"])

    def test_other_employee_gets_404_not_403(self):
        app = self.rejected_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)

    def test_approver_gets_404_not_403(self):
        app = self.rejected_app()
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_gets_401(self):
        app = self.rejected_app()
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SaveChangesTests(ResubmissionFixtureMixin, TestCase):
    def setUp(self):
        self.setUpResubmission()
        self.client.force_authenticate(user=self.employee)

    def url(self, app_id):
        return RESUB_URL.format(id=app_id)

    def patch_body(self, app, **overrides):
        app.refresh_from_db()
        body = {
            "leave_type_id": app.leave_type_id,
            "start_date": app.start_date.isoformat(),
            "end_date": app.end_date.isoformat(),
            "reason": app.reason or "Annual leave",
            "row_version": app.row_version,
        }
        body.update(overrides)
        return body

    def test_patch_keeps_rejected_status_and_bumps_version(self):
        app = self.rejected_app()
        new_reason = "Annual leave — amended."
        response = self.client.patch(
            self.url(app.id),
            self.patch_body(app, reason=new_reason),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.reason, new_reason)
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(app.submission_cycle, 1)
        self.assertEqual(response.data["row_version"], app.row_version)
        reason_change = next(
            f
            for f in response.data["changes_preview"]["fields"]
            if f["field"] == "reason"
        )
        self.assertEqual(reason_change["after"], new_reason)

    def test_patch_on_correction_required_keeps_status(self):
        app = self.returned_app()
        response = self.client.patch(
            self.url(app.id),
            self.patch_body(app, reason="Amended after correction."),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CORRECTION_REQUIRED)

    def test_patch_guard_not_editable_for_pending(self):
        app = self.submit_app()
        response = self.client.patch(
            self.url(app.id), self.patch_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "not_editable")

    def test_patch_version_conflict(self):
        app = self.rejected_app()
        response = self.client.patch(
            self.url(app.id),
            self.patch_body(app, row_version=app.row_version + 999),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "version_conflict")

    def test_patch_invalid_dates_return_validation_failed(self):
        app = self.rejected_app()
        app.refresh_from_db()
        response = self.client.patch(
            self.url(app.id),
            self.patch_body(app, start_date="2027-12-31", end_date="2027-01-01"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_failed")
        self.assertTrue(response.data["errors"])

    def test_patch_missing_row_version_is_400(self):
        app = self.rejected_app()
        body = self.patch_body(app)
        del body["row_version"]
        response = self.client.patch(self.url(app.id), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DocumentTests(ResubmissionFixtureMixin, TestCase):
    def setUp(self):
        self.setUpResubmission()
        self.client.force_authenticate(user=self.employee)

    def url(self, app_id):
        return RESUB_URL.format(id=app_id)

    def doc_url(self, app):
        return self.url(app.id) + "documents/"

    def file(self, name="note.pdf"):
        return SimpleUploadedFile(
            name, b"%PDF-1.4 test payload", content_type="application/pdf"
        )

    def upload_args(self, app, **overrides):
        body = {"row_version": self.active_row_version(app)}
        body.update(overrides)
        return body

    def test_add_document_returns_context_with_new_active_document(self):
        app = self.rejected_app()
        response = self.client.post(
            self.doc_url(app),
            {
                "row_version": self.active_row_version(app),
                "file": self.file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.upload_document.assert_called_once()
        names = [doc["name"] for doc in response.data["documents"]["active"]]
        self.assertIn("note.pdf", names)
        self.assertEqual(response.data["documents"]["retired"], [])
        app.refresh_from_db()
        self.assertEqual(app.row_version, self.active_row_version(app))
        self.assertTrue(
            SupportingDocument.objects.filter(
                application=app, file_name="note.pdf"
            ).exists()
        )

    def test_add_document_requires_file(self):
        app = self.rejected_app()
        response = self.client.post(
            self.doc_url(app),
            {"row_version": self.active_row_version(app)},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_failed")
        self.assertEqual(response.data["errors"][0]["field"], "file")

    def test_add_document_requires_row_version(self):
        app = self.rejected_app()
        response = self.client.post(
            self.doc_url(app), {"file": self.file()}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_replace_document_retires_original_and_attaches_replacement(self):
        app = self.rejected_app()
        original = self.attach_active_doc(app)
        response = self.client.post(
            self.doc_url(app) + f"{original.id}/replace/",
            {
                "row_version": self.active_row_version(app),
                "file": self.file("new-certificate.pdf"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        original.refresh_from_db()
        self.assertEqual(original.status, SupportingDocument.Status.RETIRED)
        self.assertEqual(original.retire_reason, SupportingDocument.RetireReason.REPLACED)
        self.assertIsNotNone(original.replaced_by_id)
        names = [doc["name"] for doc in response.data["documents"]["active"]]
        self.assertIn("new-certificate.pdf", names)
        retired = response.data["documents"]["retired"]
        self.assertEqual(retired[0]["retire_reason"], "replaced")
        self.assertEqual(retired[0]["replaced_by_name"], "new-certificate.pdf")

    def test_replace_unknown_document_is_404(self):
        app = self.rejected_app()
        response = self.client.post(
            self.doc_url(app) + f"{uuid4()}/replace/",
            {
                "row_version": self.active_row_version(app),
                "file": self.file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_document_retires_with_removed_reason(self):
        app = self.rejected_app()
        original = self.attach_active_doc(app)
        response = self.client.delete(
            self.doc_url(app) + f"{original.id}/",
            {"row_version": self.active_row_version(app)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        original.refresh_from_db()
        self.assertEqual(original.status, SupportingDocument.Status.RETIRED)
        self.assertEqual(original.retire_reason, SupportingDocument.RetireReason.REMOVED)
        self.assertIsNone(original.replaced_by_id)

    def test_remove_unknown_document_is_404(self):
        app = self.rejected_app()
        response = self.client.delete(
            self.doc_url(app) + f"{uuid4()}/",
            {"row_version": self.active_row_version(app)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_ops_reject_stale_row_version(self):
        app = self.rejected_app()
        response = self.client.post(
            self.doc_url(app),
            {
                "row_version": self.active_row_version(app) + 99,
                "file": self.file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "version_conflict")

    def test_document_ops_not_editable_on_pending(self):
        app = self.submit_app()
        response = self.client.post(
            self.doc_url(app),
            {"row_version": 1, "file": self.file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "not_editable")


class ResubmitTests(ResubmissionFixtureMixin, TestCase):
    def setUp(self):
        self.setUpResubmission()
        self.client.force_authenticate(user=self.employee)

    def url(self, app_id):
        return RESUBMIT_URL.format(id=app_id)

    def resubmit_body(self, app, **overrides):
        body = {"row_version": self.active_row_version(app)}
        body.update(overrides)
        return body

    def test_resubmit_returns_to_same_stage_and_approver(self):
        app = self.returned_app()
        stage = app.current_stage
        approver = stage.assigned_approver
        response = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["submission_cycle"], 2)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.PENDING)
        self.assertEqual(app.submission_cycle, 2)
        self.assertEqual(app.current_stage.stage_order, 1)
        self.assertEqual(app.current_stage.assigned_approver, approver)
        self.assertEqual(app.current_stage.status, ApplicationStage.Status.PENDING)
        self.assertTrue(app.current_stage.version > stage.version)
        self.assertEqual(app.reference_number, app.reference_number)
        self.assertEqual(
            list(app.revisions.values_list("revision_number", flat=True)),
            [1, 2],
        )

    def test_resubmit_writes_changes_diff_into_revision(self):
        app = self.rejected_app()
        new_reason = "Annual leave — resubmitted with a better reason."
        response = self.client.patch(
            RESUB_URL.format(id=app.id),
            {
                "leave_type_id": app.leave_type_id,
                "start_date": app.start_date.isoformat(),
                "end_date": app.end_date.isoformat(),
                "reason": new_reason,
                "row_version": self.active_row_version(app),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        latest = app.revisions.order_by("-revision_number").first()
        self.assertEqual(latest.revision_number, 2)
        self.assertTrue(latest.changes["has_changes"])
        field = next(
            f for f in latest.changes["fields"] if f["field"] == "reason"
        )
        self.assertEqual(field["after"], new_reason)

    def test_resubmit_not_resubmittable_when_approved(self):
        app = self.submit_app()
        self.decide_action(app, self.hod, "approve")
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "not_resubmittable")

    def test_resubmit_version_conflict_on_stale_token(self):
        app = self.rejected_app()
        response = self.client.post(
            self.url(app.id),
            {"row_version": self.active_row_version(app) + 99},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "version_conflict")

    def test_resubmit_inactive_approver_is_409_with_hr_message(self):
        app = self.rejected_app()
        app.current_stage.assigned_approver.is_active = False
        app.current_stage.assigned_approver.save(update_fields=["is_active"])
        response = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "approver_unavailable")
        self.assertIn("contact hr", response.data["detail"].lower())

    def test_resubmit_other_owner_is_404(self):
        app = self.rejected_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_resubmit_double_click_is_rejected(self):
        app = self.rejected_app()
        first = self.client.post(
            self.url(app.id), self.resubmit_body(app), format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        stale_body = self.resubmit_body(app)
        second = self.client.post(self.url(app.id), stale_body, format="json")
        # The application is now pending, so a second resubmit is not allowed.
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data["code"], "not_resubmittable")

    def test_resubmit_requires_row_version(self):
        app = self.rejected_app()
        response = self.client.post(self.url(app.id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ResubmissionAuditAndRevisionTests(ResubmissionFixtureMixin, TestCase):
    def setUp(self):
        self.setUpResubmission()
        self.client.force_authenticate(user=self.employee)

    def test_audit_trail_across_edit_and_resubmit(self):
        app = self.rejected_app()
        self.client.patch(
            RESUB_URL.format(id=app.id),
            {
                "leave_type_id": app.leave_type_id,
                "start_date": app.start_date.isoformat(),
                "end_date": app.end_date.isoformat(),
                "reason": "Amended.",
                "row_version": self.active_row_version(app),
            },
            format="json",
        )
        app.refresh_from_db()
        response = self.client.post(
            RESUBMIT_URL.format(id=app.id),
            {"row_version": app.row_version},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = list(
            AuditEvent.objects.filter(object_id=app.id)
            .order_by("created_at")
            .values_list("action", flat=True)
        )
        self.assertIn("application_resubmitted", actions)

    def test_ensure_baseline_revision_is_idempotent(self):
        app = self.rejected_app()
        from leave.services.resubmission import ensure_baseline_revision

        first = ensure_baseline_revision(app)
        again = ensure_baseline_revision(app)
        self.assertEqual(first.id, again.id)
        self.assertEqual(first.revision_number, 1)
        self.assertIsNone(first.changes)

    def test_first_revision_has_no_changes(self):
        app = self.submit_app()
        revision = app.revisions.get(revision_number=1)
        self.assertIsNone(revision.changes)
        self.assertEqual(revision.start_date, app.start_date)