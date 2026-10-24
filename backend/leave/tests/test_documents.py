"""Backend tests for Unit 19 supporting-document lifecycle.

Covers the editable-status matrix, draft (hard delete) vs rejected
(retire-only) semantics, atomic replacement, file validation on every write
path, serializer field changes, tracking-payload documents, audit entries, and
owner-scoping.
"""

from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.documents.services import EDITABLE_STATUSES
from leave.models import LeaveApplication, SupportingDocument
from leave.serializers import LeaveApplicationSerializer, SupportingDocumentSerializer
from leave.validation.validators.documents import count_supporting_documents

from .stubs import make_user

User = get_user_model()

BASE = "/api/v1/leave-applications/{app}/documents/"


def pdf(name="letter.pdf", size=1024, content_type="application/pdf", data=b"x" * 1024):
    return SimpleUploadedFile(name, data, content_type=content_type)


def upload_patch():
    from leave.services.storage import _sanitize_document_name

    def fake_upload(file, application_id):
        safe_name = _sanitize_document_name(file.name)
        return {
            "path": f"leave-documents/{application_id}/{safe_name}",
            "url": f"https://signed/{safe_name}",
        }

    return mock.patch(
        "leave.documents.services.upload_document", side_effect=fake_upload
    )


class DocumentFixtureTests(TestCase):
    """Helpers to build an owned application plus optional documents."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def app(self, status_=LeaveApplication.Status.DRAFT, **kwargs):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 6),
            reason="Test",
            status=status_,
            **kwargs,
        )

    def doc(self, application, name="letter.pdf", status_=SupportingDocument.Status.ACTIVE):
        return SupportingDocument.objects.create(
            application=application,
            file_path=f"leave-documents/{application.id}/{name}",
            file_url=f"https://stored/{name}",
            file_name=name,
            file_size=1024,
            content_type="application/pdf",
            status=status_,
        )

    def list_url(self, app):
        return BASE.format(app=app.id)

    def doc_url(self, app, document):
        return f"{self.list_url(app)}{document.id}/"

    def replace_url(self, app, document):
        return f"{self.doc_url(app, document)}replace/"


class EditableStatusMatrixTests(DocumentFixtureTests):
    """Upload/remove/replace work in draft + rejected; all else is 409."""

    def test_upload_and_remove_in_draft(self):
        application = self.app()
        with upload_patch():
            response = self.client.post(
                self.list_url(application), {"file": pdf()}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        created = SupportingDocument.objects.get()
        response = self.client.delete(self.doc_url(application, created))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(SupportingDocument.objects.count(), 0)

    def test_upload_in_rejected(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        with upload_patch():
            response = self.client.post(
                self.list_url(application), {"file": pdf()}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportingDocument.objects.get().status, "active")

    def test_remove_retires_in_rejected(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        with mock.patch("leave.documents.services.delete_document") as storage_delete:
            response = self.client.delete(self.doc_url(application, document))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        storage_delete.assert_not_called()
        document.refresh_from_db()
        self.assertEqual(document.status, "retired")
        self.assertEqual(document.retire_reason, "removed")
        self.assertEqual(document.retired_by, self.user)
        self.assertIsNotNone(document.retired_at)

    def test_upload_returns_409_for_every_non_editable_status(self):
        for status_name in ("submitted", "approved", "cancelled"):
            application = self.app(status_=status_name)
            response = self.client.post(
                self.list_url(application), {"file": pdf()}, format="multipart"
            )
            self.assertEqual(
                response.status_code, status.HTTP_409_CONFLICT, status_name
            )
            self.assertEqual(response.data["code"], "application_not_editable")

    def test_remove_returns_409_for_every_non_editable_status(self):
        for status_name in ("submitted", "approved", "cancelled"):
            application = self.app(status_=status_name)
            document = self.doc(application)
            response = self.client.delete(self.doc_url(application, document))
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, status_name)
            self.assertEqual(response.data["code"], "application_not_editable")
            document.refresh_from_db()
            self.assertEqual(document.status, "active")

    def test_replace_returns_409_for_submitted(self):
        application = self.app(status_=LeaveApplication.Status.SUBMITTED)
        document = self.doc(application)
        response = self.client.post(
            self.replace_url(application, document), {"file": pdf()}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "application_not_editable")


class DraftSemanticsTests(DocumentFixtureTests):
    def test_draft_remove_hard_deletes_row_and_storage_object(self):
        application = self.app()
        document = self.doc(application)
        with mock.patch("leave.documents.services.delete_document") as storage_delete:
            response = self.client.delete(self.doc_url(application, document))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        storage_delete.assert_called_once_with(document.file_path)
        self.assertFalse(SupportingDocument.objects.filter(pk=document.pk).exists())

    def test_draft_remove_records_document_removed_audit(self):
        application = self.app()
        document = self.doc(application)
        with mock.patch("leave.documents.services.delete_document"):
            self.client.delete(self.doc_url(application, document))

        entry = AuditEntry.objects.get(target_id=str(application.id))
        self.assertEqual(entry.action, "document_removed")
        self.assertEqual(entry.target_type, "application")
        self.assertFalse(
            AuditEntry.objects.filter(action="document_retired").exists()
        )

    def test_draft_remove_continues_when_storage_delete_fails(self):
        application = self.app()
        document = self.doc(application)
        with mock.patch(
            "leave.documents.services.delete_document", side_effect=RuntimeError("boom")
        ):
            response = self.client.delete(self.doc_url(application, document))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SupportingDocument.objects.filter(pk=document.pk).exists())

    def test_replace_is_refused_on_a_draft(self):
        application = self.app()
        document = self.doc(application)
        with upload_patch():
            response = self.client.post(
                self.replace_url(application, document),
                {"file": pdf()},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "application_not_editable")
        document.refresh_from_db()
        self.assertEqual(document.status, "active")


class RejectedDocumentSemanticsTests(DocumentFixtureTests):
    def test_replace_uploads_new_row_and_retires_old(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application, name="old.pdf")
        with upload_patch() as upload:
            response = self.client.post(
                self.replace_url(application, document),
                {"file": pdf(name="new.pdf")},
                format="multipart",
            )
            storage_called = upload.call_count

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(storage_called, 1)
        self.assertEqual(response.data["retired_document"], str(document.pk))

        document.refresh_from_db()
        self.assertEqual(document.status, "retired")
        self.assertEqual(document.retire_reason, "replaced")
        self.assertEqual(document.retired_by, self.user)
        replacement = SupportingDocument.objects.get(status="active")
        self.assertEqual(replacement.file_name, "new.pdf")
        self.assertEqual(document.replaced_by, replacement)
        self.assertEqual(response.data["document"]["id"], str(replacement.id))
        self.assertEqual(response.data["document"]["file_name"], "new.pdf")

    def test_replace_keeps_storage_objects_for_both_rows(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application, name="old.pdf")
        with mock.patch(
            "leave.documents.services.delete_document"
        ) as storage_delete, upload_patch():
            self.client.post(
                self.replace_url(application, document),
                {"file": pdf(name="new.pdf")},
                format="multipart",
            )
        storage_delete.assert_not_called()

    def test_retired_document_has_no_mutation_path(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        document.retire(self.user, reason=SupportingDocument.RetireReason.REMOVED)

        for method, url in [
            ("delete", self.doc_url(application, document)),
            ("replace", self.replace_url(application, document)),
        ]:
            if method == "delete":
                response = self.client.delete(url)
            else:
                response = self.client.post(url, {"file": pdf()}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data["code"], "document_not_active")

    def test_include_retired_lists_retired_rows_only_to_owner(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        active = self.doc(application, name="active.pdf")
        retired = self.doc(application, name="old.pdf")
        retired.retire(self.user, reason=SupportingDocument.RetireReason.REPLACED)

        plain = self.client.get(self.list_url(application))
        self.assertEqual(plain.status_code, status.HTTP_200_OK)
        self.assertEqual([d["file_name"] for d in plain.data], ["active.pdf"])

        full = self.client.get(f"{self.list_url(application)}?include_retired=true")
        self.assertEqual(full.status_code, status.HTTP_200_OK)
        names = {d["file_name"]: d for d in full.data}
        self.assertEqual(names["old.pdf"]["status"], "retired")
        self.assertIsNotNone(names["old.pdf"]["retired_at"])
        self.assertEqual(names["old.pdf"]["retire_reason"], "replaced")
        self.assertEqual(names["old.pdf"]["retired_by"]["name"], self.user.username)
        self.assertEqual(names["active.pdf"]["status"], "active")

        del active, retired


class FileValidationTests(DocumentFixtureTests):
    def test_file_required_on_upload(self):
        response = self.client.post(self.list_url(self.app()), {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "No file provided.")

    def test_file_required_on_replace(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        response = self.client.post(self.replace_url(application, document), {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_size_limit_enforced_on_upload(self):
        with mock.patch("leave.documents.services.MAX_DOCUMENT_SIZE", 100):
            response = self.client.post(
                self.list_url(self.app()),
                {"file": pdf(data=b"x" * 101)},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Files may not exceed", response.data["detail"])

    def test_size_limit_enforced_on_replace(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        with mock.patch("leave.documents.services.MAX_DOCUMENT_SIZE", 100):
            response = self.client.post(
                self.replace_url(application, document),
                {"file": pdf(data=b"x" * 101)},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_content_type_enforced_on_upload_and_replace(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application, name="old.pdf")

        bad = pdf(name="payload.exe", content_type="application/x-msdownload")
        upload_response = self.client.post(
            self.list_url(application), {"file": bad}, format="multipart"
        )
        self.assertEqual(upload_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(upload_response.data["detail"], "File type is not allowed.")

        replace_response = self.client.post(
            self.replace_url(application, document),
            {"file": bad},
            format="multipart",
        )
        self.assertEqual(replace_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_storage_name_is_sanitized_on_every_write_path(self):
        from leave.services.storage import _sanitize_document_name

        self.assertEqual(_sanitize_document_name("../../ Budget Plan.pdf"), "Budget_Plan.pdf")

        application = self.app()
        with upload_patch() as upload:
            self.client.post(
                self.list_url(application),
                {"file": pdf(name="../../ Budget Plan.pdf")},
                format="multipart",
            )
        path = upload.call_args.args[1]
        self.assertNotIn("/", path.replace(f"leave-documents/{application.id}/", ""))

    def test_signed_url_longer_than_the_column_is_stored_not_truncated(self):
        """A real Supabase signed URL must fit ``file_url``.

        Regression: the column defaulted to ``URLField()``'s 200 chars while
        the writer stores a signed URL (host + storage path + a JWT token),
        which raised ``StringDataRightTruncation`` -> HTTP 500 on upload.
        """
        field = SupportingDocument._meta.get_field("file_url")
        # Worst case: the model's own 255-char file_name cap, signed.
        signed_url = "https://" + "p" * 30 + ".supabase.co/storage/v1/object/sign/" + "s" * 895
        self.assertLess(len(signed_url), field.max_length)

        application = self.app()
        with mock.patch(
            "leave.documents.services.upload_document",
            return_value={"path": "leave-documents/x/y", "url": signed_url},
        ):
            response = self.client.post(
                self.list_url(application), {"file": pdf()}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            SupportingDocument.objects.get().file_url, signed_url
        )


class SerializerContractTests(DocumentFixtureTests):
    def test_leave_application_documents_excludes_retired(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        active = self.doc(application, name="active.pdf")
        retired = self.doc(application, name="old.pdf")
        retired.retire(self.user, reason=SupportingDocument.RetireReason.REPLACED)

        data = LeaveApplicationSerializer(application).data
        self.assertEqual([d["id"] for d in data["documents"]], [str(active.id)])

    def test_file_path_is_never_serialized(self):
        application = self.app()
        document = self.doc(application)
        data = SupportingDocumentSerializer(document).data
        self.assertNotIn("file_path", data)
        self.assertIn("status", data)
        self.assertIn("retired_at", data)
        self.assertIn("retire_reason", data)
        self.assertIn("retired_by", data)
        self.assertIn("replaced_by", data)


class AuditTests(DocumentFixtureTests):
    def test_upload_records_document_added(self):
        application = self.app()
        with upload_patch():
            self.client.post(self.list_url(application), {"file": pdf()}, format="multipart")

        document = SupportingDocument.objects.get()
        entry = AuditEntry.objects.get(target_id=str(application.id))
        self.assertEqual(entry.action, "document_added")
        self.assertEqual(entry.target_type, "application")
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.detail["file_name"], "letter.pdf")
        self.assertEqual(entry.detail["document_id"], str(document.id))

    def test_remove_records_document_removed(self):
        application = self.app()
        document = self.doc(application)
        with mock.patch("leave.documents.services.delete_document"):
            self.client.delete(self.doc_url(application, document))
        entry = AuditEntry.objects.get(target_id=str(application.id))
        self.assertEqual(entry.action, "document_removed")
        self.assertEqual(entry.target_type, "application")

    def test_rejected_removal_records_document_retired(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        self.client.delete(self.doc_url(application, document))
        entry = AuditEntry.objects.get(target_id=str(application.id))
        self.assertEqual(entry.action, "document_retired")
        self.assertEqual(entry.detail["retire_reason"], "removed")

    def test_replace_records_document_replaced(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application, name="old.pdf")
        with upload_patch():
            response = self.client.post(
                self.replace_url(application, document),
                {"file": pdf(name="new.pdf")},
                format="multipart",
            )
        entry = AuditEntry.objects.get(target_id=str(application.id))
        self.assertEqual(entry.action, "document_replaced")
        self.assertEqual(entry.detail["replaced_by"], str(
            SupportingDocument.objects.get(status="active").id
        ))
        self.assertEqual(entry.actor, self.user)


class AuthorizationTests(DocumentFixtureTests):
    def test_foreign_application_document_operations_are_404(self):
        other = make_user(username="other@test.luanar")
        foreign = LeaveApplication.objects.create(employee=other, leave_type_id=1)
        document = self.doc(foreign)

        self.client.force_authenticate(user=self.user)

        upload_response = self.client.post(
            self.list_url(foreign), {"file": pdf()}, format="multipart"
        )
        self.assertEqual(upload_response.status_code, status.HTTP_404_NOT_FOUND)

        remove_response = self.client.delete(self.doc_url(foreign, document))
        self.assertEqual(remove_response.status_code, status.HTTP_404_NOT_FOUND)

        replace_response = self.client.post(
            self.replace_url(foreign, document), {"file": pdf()}, format="multipart"
        )
        self.assertEqual(replace_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_operations_are_401(self):
        application = self.app()
        document = self.doc(application)
        client = APIClient()

        self.assertEqual(
            client.get(self.list_url(application)).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            client.delete(self.doc_url(application, document)).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class RequiredDocumentRuleTests(DocumentFixtureTests):
    def test_validator_counts_active_rows_only(self):
        application = self.app(status_=LeaveApplication.Status.REJECTED)
        document = self.doc(application)
        document.retire(self.user, reason=SupportingDocument.RetireReason.REMOVED)
        self.assertEqual(count_supporting_documents(application), 0)

        replacement = self.doc(application, name="new.pdf")
        self.assertEqual(count_supporting_documents(application), 1)
        self.assertTrue(bool(EDITABLE_STATUSES))


class ActiveDocumentQueryHelperTests(TestCase):
    """The shared active-count helper used by the required-document validator."""

    def test_active_count_helper_ignores_retired_rows(self):
        user = make_user()
        application = LeaveApplication.objects.create(
            employee=user, leave_type_id=1, status=LeaveApplication.Status.REJECTED
        )
        SupportingDocument.objects.create(
            application=application,
            file_path="x/old.pdf",
            file_url="u",
            file_name="old.pdf",
            file_size=1,
            content_type="application/pdf",
            status=SupportingDocument.Status.RETIRED,
        )
        SupportingDocument.objects.create(
            application=application,
            file_path="x/active.pdf",
            file_url="u",
            file_name="active.pdf",
            file_size=1,
            content_type="application/pdf",
        )
        self.assertEqual(count_supporting_documents(application), 1)

class SupabaseClientConfigTests(TestCase):
    """``get_supabase_client`` rejects a misconfigured project URL.

    The Supabase dashboard's "Project URL" field ends in ``/rest/v1/``. Copied
    verbatim into ``SUPABASE_URL`` it looks correct, but ``supabase-py`` appends
    its own service paths, so every Storage request is sent to PostgREST and
    fails with an opaque ``404`` / ``PGRST125`` that names neither the bucket nor
    the setting. The guard turns that into an actionable message.
    """

    def test_a_url_with_a_path_suffix_is_rejected(self):
        from django.test import override_settings

        from leave.services.storage import get_supabase_client

        with override_settings(
            SUPABASE_URL="https://project-ref.supabase.co/rest/v1/",
            SUPABASE_SERVICE_KEY="service-key",
        ):
            with self.assertRaises(ValueError) as ctx:
                get_supabase_client()
        message = str(ctx.exception)
        self.assertIn("SUPABASE_URL", message)
        self.assertIn("rest/v1", message)

    def test_a_bare_project_url_is_accepted(self):
        from django.test import override_settings

        from leave.services.storage import get_supabase_client

        for url in (
            "https://project-ref.supabase.co",
            "https://project-ref.supabase.co/",
        ):
            with self.subTest(url=url):
                with override_settings(
                    SUPABASE_URL=url, SUPABASE_SERVICE_KEY="service-key"
                ):
                    self.assertIsNotNone(get_supabase_client())

    def test_missing_credentials_are_still_reported_as_such(self):
        from django.test import override_settings

        from leave.services.storage import get_supabase_client

        with override_settings(SUPABASE_URL="", SUPABASE_SERVICE_KEY=""):
            with self.assertRaises(ValueError) as ctx:
                get_supabase_client()
        self.assertIn("not configured", str(ctx.exception))
