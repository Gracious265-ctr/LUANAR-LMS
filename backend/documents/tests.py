from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User

from .admin import LeaveDocumentTemplateAdmin
from .models import LeaveDocumentTemplate
from .serializers import LeaveDocumentTemplateSerializer
from .services import (
    ALLOWED_FIELD_KEYS,
    DEFAULT_FIELDS,
    DEFAULT_SIGNATURE_AREAS,
    FIELD_CATALOG,
    MAX_SIGNATURE_AREAS,
    get_template,
)

SEED_PASSWORD = "testpass123"

API_URL = "/api/v1/leave-document-template/"


def make_user(role, username):
    return User.objects.create_user(
        username=username,
        email=username,
        password=SEED_PASSWORD,
        first_name="Test",
        last_name=role.title(),
        role=role,
    )


class GetTemplateTests(TestCase):
    """Service-level singleton default materialization."""

    def test_first_access_creates_the_default_template(self):
        template = get_template()
        self.assertEqual(LeaveDocumentTemplate.objects.count(), 1)
        self.assertEqual(template.fields, DEFAULT_FIELDS)
        self.assertEqual(template.signature_areas, DEFAULT_SIGNATURE_AREAS)
        self.assertEqual(len(FIELD_CATALOG), len(ALLOWED_FIELD_KEYS))

    def test_repeated_access_returns_the_same_singleton(self):
        get_template()
        second = get_template()
        self.assertEqual(LeaveDocumentTemplate.objects.count(), 1)
        self.assertEqual(second.pk, 1)


class SerializerTests(TestCase):
    """Field-catalog and list validation for template configuration."""

    def test_default_template_configuration_is_valid(self):
        template = get_template()
        serializer = LeaveDocumentTemplateSerializer(
            data={
                "title": template.title,
                "header": template.header,
                "intro": template.intro,
                "fields": template.fields,
                "closing": template.closing,
                "signature_areas": template.signature_areas,
                "footer": template.footer,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_unknown_field_key_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"fields": [{"key": "salary", "label": "Salary"}]},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("unknown data field", serializer.errors["fields"][0])

    def test_duplicate_field_key_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={
                "fields": [
                    {"key": "employee_name", "label": "Name"},
                    {"key": "employee_name", "label": "Employee"},
                ]
            },
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("repeats", serializer.errors["fields"][0])

    def test_blank_field_label_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"fields": [{"key": "employee_name", "label": "   "}]},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non-blank", serializer.errors["fields"][0])

    def test_duplicate_labels_across_keys_kept(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={
                "fields": [
                    {"key": "start_date", "label": "Date"},
                    {"key": "end_date", "label": "Date"},
                ]
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_blank_title_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"title": "   "}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("title", serializer.errors)

    def test_empty_fields_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"fields": []}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("At least one", serializer.errors["fields"][0])

    def test_fields_exceeding_catalog_size_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"fields": DEFAULT_FIELDS + [{"key": "reference", "label": "Repeat"}]},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("fields", serializer.errors)

    def test_blank_signature_label_rejected(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={"signature_areas": [{"label": "  "}]}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non-blank", serializer.errors["signature_areas"][0])

    def test_too_many_signature_areas_rejected(self):
        areas = [{"label": f"Signature {i}"} for i in range(9)]
        serializer = LeaveDocumentTemplateSerializer(
            data={"signature_areas": areas}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("At most 8", serializer.errors["signature_areas"][0])

    def test_order_of_fields_is_preserved(self):
        serializer = LeaveDocumentTemplateSerializer(
            data={
                "fields": [
                    {"key": "request_reason", "label": "Reason"},
                    {"key": "reference", "label": "Reference"},
                ]
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        keys = [row["key"] for row in serializer.validated_data["fields"]]
        self.assertEqual(keys, ["request_reason", "reference"])


class EndpointTests(TestCase):
    """HR-only singleton read/update and preview endpoints."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr_user = make_user(User.Role.HR, "hr@test.luanar")
        self.employee_user = make_user(User.Role.EMPLOYEE, "employee@test.luanar")

    def test_read_requires_authentication(self):
        response = self.client.get(API_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_forbidden_for_employee(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(API_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_returns_the_singleton_default_for_hr(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(API_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["fields"], DEFAULT_FIELDS)
        self.assertEqual(
            response.data["signature_areas"], DEFAULT_SIGNATURE_AREAS
        )
        self.assertIn("updated_at", response.data)

    def test_patch_updates_wording_and_order(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            API_URL,
            {
                "title": "APPROVED LEAVE CERTIFICATE",
                "intro": "Official opening wording.",
                "fields": [
                    {"key": "reference", "label": "Reference"},
                    {"key": "employee_name", "label": "Employee Name"},
                ],
                "signature_areas": [{"label": "For: University Registrar"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "APPROVED LEAVE CERTIFICATE")
        self.assertEqual(
            [row["key"] for row in response.data["fields"]],
            ["reference", "employee_name"],
        )

    def test_patch_rejects_unknown_field_key(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            API_URL,
            {"fields": [{"key": "salary", "label": "Salary"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fields", response.data)

    def test_patch_of_signature_areas_alone_succeeds(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            API_URL,
            {"signature_areas": [{"label": "For: Registrar"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            LeaveDocumentTemplate.objects.get(pk=1).signature_areas,
            [{"label": "For: Registrar"}],
        )

    def test_patch_never_stores_values(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            API_URL,
            {
                "fields": [
                    {"key": "employee_name", "label": "Employee", "value": "Jane"}
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stored = LeaveDocumentTemplate.objects.get(pk=1)
        self.assertEqual(stored.fields[0], {"key": "employee_name", "label": "Employee"})

    def test_read_exposes_the_backend_field_catalog(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(API_URL)
        self.assertEqual(response.data["available_fields"], FIELD_CATALOG)

    def test_patch_response_also_carries_the_field_catalog(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.patch(
            API_URL, {"title": "UPDATED"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_fields"], FIELD_CATALOG)


class AdminTests(TestCase):
    """Admin inspector reflects the backend state and forbids edits."""

    def setUp(self):
        self.site = AdminSite()
        self.model_admin = LeaveDocumentTemplateAdmin(
            LeaveDocumentTemplate, self.site
        )

    def test_admin_lists_every_field_read_only(self):
        self.assertIn("title", self.model_admin.readonly_fields)
        self.assertIn("fields", self.model_admin.readonly_fields)
        self.assertIn("signature_areas", self.model_admin.readonly_fields)

    def test_admin_cannot_add_change_or_delete(self):
        self.assertFalse(self.model_admin.has_add_permission(None))
        self.assertFalse(self.model_admin.has_change_permission(None, None))
        self.assertFalse(self.model_admin.has_delete_permission(None, None))

# ---------------------------------------------------------------------------
# Unit 23b — approved leave documents
# ---------------------------------------------------------------------------

from datetime import date
from unittest import mock
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from audit.models import AuditEntry
from leave.models import LeaveApplication, LeaveType
from leave.services.storage import upload_bytes, upload_document
from storage3.exceptions import StorageApiError
from users.models import User

from .models import ApprovedLeaveDocument, ApprovedLeaveDocumentLockedError
from .services import (
    APPROVED_DOCUMENT_FILENAME,
    document_values,
    enqueue_approved_document_render,
    render_approved_document_pdf,
)
from .tasks import render_approved_document

DOCUMENT_URL = "/api/v1/approved-leave-documents/by-application/{pk}/"
HR_DOCUMENT_URL = "/api/v1/hr/approved-leave-documents/by-application/{pk}/"


class _FakeBucket:
    """Records uploads so tests can assert the storage key (D6)."""

    def __init__(self):
        self.uploads = {}

    def upload(self, path, data, opts):
        self.uploads[path] = (data, opts)

    def create_signed_url(self, path, expiry):
        return {"signedURL": f"https://signed/{path}"}


class _FakeClient:
    def __init__(self):
        self.bucket = _FakeBucket()
        self.storage = self

    def from_(self, bucket):
        return self.bucket


def annual_leave_type():
    leave_type, _created = LeaveType.objects.get_or_create(
        name="Annual leave",
        defaults={"code": "annual-leave"},
    )
    return leave_type


def approved_application(
    employee, *, status=LeaveApplication.Status.APPROVED, reference="LV-2026-004711"
):
    leave_type = annual_leave_type()
    return LeaveApplication.objects.create(
        employee=employee,
        leave_type_id=leave_type.pk,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 23),
        working_days=15,
        calendar_days=19,
        reason="Personal leave",
        financial_year_label="2026/2027",
        status=status,
        reference_number=reference,
        rules_snapshot={"leave_type": {"deducts_annual_balance": True}},
    )


class StoragePrefixTests(TestCase):
    """The generated document lands under its own prefix (D6)."""

    def setUp(self):
        self.client = _FakeClient()
        self.app_id = str(uuid4())

    def test_upload_document_keeps_the_supporting_document_prefix_by_default(self):
        with mock.patch(
            "leave.services.storage.get_supabase_client", return_value=self.client
        ):
            result = upload_document(
                SimpleUploadedFile("notes.pdf", b"%PDF", content_type="application/pdf"),
                self.app_id,
            )
        self.assertTrue(
            result["path"].startswith(f"leave-documents/{self.app_id}/")
        )

    def test_upload_document_honours_an_explicit_prefix(self):
        with mock.patch(
            "leave.services.storage.get_supabase_client", return_value=self.client
        ):
            result = upload_document(
                SimpleUploadedFile("notes.pdf", b"%PDF", content_type="application/pdf"),
                self.app_id,
                prefix="approved/",
            )
        self.assertTrue(result["path"].startswith(f"approved/{self.app_id}/"))

    def test_upload_bytes_stores_under_the_approved_prefix(self):
        with mock.patch(
            "leave.services.storage.get_supabase_client", return_value=self.client
        ):
            result = upload_bytes(
                b"%PDF-1.4 generated",
                APPROVED_DOCUMENT_FILENAME,
                prefix="approved/",
                application_id=self.app_id,
            )
        path = result["path"]
        self.assertTrue(path.startswith(f"approved/{self.app_id}/"))
        self.assertTrue(path.endswith(f"-{APPROVED_DOCUMENT_FILENAME}"))
        data, opts = self.client.bucket.uploads[path]
        self.assertEqual(data, b"%PDF-1.4 generated")
        self.assertEqual(opts["content-type"], "application/pdf")


class DocumentValuesTests(TestCase):
    """Values come from the application, never from a catalog sample (D4)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "values_employee")
        self.application = approved_application(self.employee)

    def test_every_catalog_key_resolves(self):
        values = document_values(self.application)
        self.assertEqual(
            set(values), {field["key"] for field in FIELD_CATALOG}
        )

    def test_values_come_from_the_application_record(self):
        values = document_values(self.application)
        self.assertEqual(values["reference"], "LV-2026-004711")
        self.assertEqual(values["employee_name"], "Test Employee")
        self.assertEqual(values["leave_type"], "Annual leave")
        self.assertEqual(values["working_days"], "15")
        self.assertEqual(values["request_reason"], "Personal leave")
        self.assertEqual(values["start_date"], "2026-10-05")

    def test_a_missing_value_never_falls_back_to_the_catalog_sample(self):
        """The substitution risk D4 rules out: absent data must render blank.

        This employee has no HR profile, so the three profile-backed catalog
        keys have no value to resolve — yet the catalog carries samples for
        all of them. A sample leaking in here would put another person's data
        on an official document.
        """
        values = document_values(self.application)
        for key in ("employee_grade", "designation", "department"):
            sample = next(f["sample"] for f in FIELD_CATALOG if f["key"] == key)
            self.assertTrue(sample, f"{key} should have a sample to leak")
            self.assertEqual(values[key], "")

    def test_approved_on_is_blank_before_the_stamp(self):
        self.assertEqual(document_values(self.application)["approved_on"], "")

    def test_approved_on_renders_as_a_local_date(self):
        self.application.approved_on = timezone.now()
        self.assertRegex(
            document_values(self.application)["approved_on"], r"^\d{4}-\d{2}-\d{2}$"
        )

    def test_missing_profile_renders_blank_rather_than_raising(self):
        values = document_values(self.application)
        self.assertEqual(values["employee_grade"], "")
        self.assertEqual(values["designation"], "")
        self.assertEqual(values["department"], "")


class RenderPdfTests(TestCase):
    """The renderer is data-driven and total (D11)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "render_employee")
        self.application = approved_application(self.employee)

    def test_renders_a_pdf(self):
        pdf = render_approved_document_pdf(self.application)
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_unknown_field_key_renders_blank_and_does_not_raise(self):
        template = get_template()
        template.fields = [{"key": "not_a_real_key", "label": "Mystery"}]
        template.save(update_fields=["fields"])
        pdf = render_approved_document_pdf(self.application)
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_template_with_no_fields_still_renders(self):
        template = get_template()
        template.fields = []
        template.signature_areas = []
        template.intro = ""
        template.closing = ""
        template.save(update_fields=["fields", "signature_areas", "intro", "closing"])
        self.assertTrue(render_approved_document_pdf(self.application).startswith(b"%PDF-"))

    def test_html_in_a_value_cannot_inject_markup(self):
        self.application.reason = "<b>bold</b> & <script>x</script>"
        self.application.save(update_fields=["reason"])
        pdf = render_approved_document_pdf(self.application)
        self.assertNotIn(b"<script>", pdf)

    def test_signature_areas_are_capped_at_the_configured_maximum(self):
        template = get_template()
        template.signature_areas = [
            {"label": f"Signer {index}"} for index in range(MAX_SIGNATURE_AREAS + 5)
        ]
        template.save(update_fields=["signature_areas"])
        self.assertTrue(render_approved_document_pdf(self.application).startswith(b"%PDF-"))


class RenderTaskTests(TestCase):
    """The task is idempotent and never breaks the approval (D5, D9)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "task_employee")
        self.application = approved_application(self.employee)
        self.application.approved_on = timezone.now()
        self.application.save(update_fields=["approved_on"])
        self.document = ApprovedLeaveDocument.objects.create(
            application=self.application,
            status=ApprovedLeaveDocument.Status.PENDING,
        )
        self.fake = _FakeClient()

    def _render(self):
        with mock.patch(
            "leave.services.storage.get_supabase_client", return_value=self.fake
        ):
            return render_approved_document(self.document.pk)

    def test_successful_render_marks_the_row_ready(self):
        self.assertEqual(self._render(), ApprovedLeaveDocument.Status.READY)
        self.document.refresh_from_db()
        self.assertTrue(self.document.is_available)
        self.assertEqual(self.document.file_name, APPROVED_DOCUMENT_FILENAME)
        self.assertEqual(self.document.content_type, "application/pdf")
        self.assertTrue(self.document.file_path.startswith(f"approved/{self.application.pk}/"))
        self.assertGreater(self.document.file_size, 0)

    def test_success_records_a_document_generated_audit_entry(self):
        self._render()
        entry = AuditEntry.objects.get(
            action=AuditEntry.Action.DOCUMENT_GENERATED,
            target_id=str(self.application.pk),
        )
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.APPLICATION)

    def test_rerunning_a_ready_render_is_a_no_op(self):
        self._render()
        first_path = ApprovedLeaveDocument.objects.get(pk=self.document.pk).file_path
        with mock.patch(
            "documents.tasks.upload_bytes", side_effect=AssertionError("re-rendered")
        ):
            self.assertEqual(
                self._render(), ApprovedLeaveDocument.Status.READY
            )
        self.assertEqual(
            ApprovedLeaveDocument.objects.get(pk=self.document.pk).file_path,
            first_path,
        )

    def test_a_render_failure_is_recorded_and_never_raised(self):
        with mock.patch(
            "documents.tasks.render_approved_document_pdf",
            side_effect=RuntimeError("supabase exploded"),
        ):
            self.assertEqual(self._render(), ApprovedLeaveDocument.Status.FAILED)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, ApprovedLeaveDocument.Status.FAILED)
        self.assertFalse(self.document.is_available)
        self.assertIn("supabase exploded", self.document.error_message)

    def test_a_failure_still_leaves_the_approval_committed(self):
        with mock.patch(
            "documents.tasks.render_approved_document_pdf",
            side_effect=RuntimeError("boom"),
        ):
            self._render()
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.status, LeaveApplication.Status.APPROVED
        )

    def test_failure_records_a_document_failed_audit_entry(self):
        with mock.patch(
            "documents.tasks.render_approved_document_pdf",
            side_effect=RuntimeError("boom"),
        ):
            self._render()
        entry = AuditEntry.objects.get(action=AuditEntry.Action.DOCUMENT_FAILED)
        self.assertIsNone(entry.actor)

    def test_error_message_is_sanitized_to_the_first_line(self):
        with mock.patch(
            "documents.tasks.render_approved_document_pdf",
            side_effect=RuntimeError("line one\nSERVICE_ROLE_KEY=secret"),
        ):
            self._render()
        self.document.refresh_from_db()
        self.assertNotIn("SERVICE_ROLE_KEY", self.document.error_message)
        self.assertIn("line one", self.document.error_message)

    def test_an_empty_render_is_treated_as_a_failure(self):
        with mock.patch(
            "documents.tasks.render_approved_document_pdf", return_value=b""
        ):
            self.assertEqual(self._render(), ApprovedLeaveDocument.Status.FAILED)


class EnqueueTests(TestCase):
    """Enqueueing is on-commit and a missing broker is survivable (D5)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "enqueue_employee")
        self.application = approved_application(self.employee)
        self.document = ApprovedLeaveDocument.objects.create(
            application=self.application
        )

    def test_nothing_is_enqueued_before_the_transaction_commits(self):
        with mock.patch("django_q.tasks.async_task") as async_task:
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_approved_document_render(self.document)
                async_task.assert_not_called()
            async_task.assert_called_once_with(
                "documents.tasks.render_approved_document", self.document.pk
            )

    def test_an_unreachable_broker_is_swallowed(self):
        with mock.patch(
            "django_q.tasks.async_task", side_effect=OSError("no broker")
        ):
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_approved_document_render(self.document)


class ApprovedDocumentAccessTests(TestCase):
    """Each audience is admitted by its own rule (D7)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "access_employee")
        self.other = make_user(User.Role.EMPLOYEE, "access_stranger")
        self.hr = make_user(User.Role.HR, "access_hr")
        self.application = approved_application(self.employee)
        self.document = ApprovedLeaveDocument.objects.create(
            application=self.application,
            status=ApprovedLeaveDocument.Status.READY,
            file_path=f"approved/{self.application.pk}/approved-leave.pdf",
            file_name=APPROVED_DOCUMENT_FILENAME,
            content_type="application/pdf",
            file_size=2048,
        )
        # A second application whose document is still pending, so the
        # not-yet-available states can be exercised without unsealing a ready
        # row (which the model deliberately forbids).
        self.pending_application = approved_application(
            self.employee, reference="LV-2026-004712"
        )
        self.pending_document = ApprovedLeaveDocument.objects.create(
            application=self.pending_application
        )
        self.ready_url = DOCUMENT_URL.format(pk=self.application.pk)
        self.hr_url = HR_DOCUMENT_URL.format(pk=self.application.pk)

    def _get(self, url, user):
        client = APIClient()
        client.force_authenticate(user=user)
        with mock.patch(
            "leave.services.storage.signed_document_url",
            return_value="https://signed/fresh",
        ):
            return client.get(url)

    def test_read_requires_authentication(self):
        self.assertEqual(APIClient().get(self.ready_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_reads_the_document(self):
        response = self._get(self.ready_url, self.employee)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["available"])
        self.assertEqual(response.data["download_url"], "https://signed/fresh")

    def test_stranger_gets_404_not_403(self):
        response = self._get(self.ready_url, self.other)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_id_is_indistinguishable_from_a_strangers_404(self):
        stranger = self._get(self.ready_url, self.other)
        unknown = self._get(DOCUMENT_URL.format(pk=uuid4()), self.other)
        self.assertEqual(stranger.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(stranger.data, unknown.data)

    def test_hr_reads_through_the_hr_route(self):
        response = self._get(self.hr_url, self.hr)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_hr_gets_403_on_the_hr_route(self):
        response = self._get(self.hr_url, self.employee)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_pending_document_reports_its_status_and_mints_no_url(self):
        response = self._get(
            DOCUMENT_URL.format(pk=self.pending_application.pk), self.employee
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])
        self.assertEqual(response.data["status"], ApprovedLeaveDocument.Status.PENDING)
        self.assertEqual(response.data["download_url"], "")

    def test_a_failed_document_reports_its_status_and_mints_no_url(self):
        self.pending_document.mark_failed("storage unavailable")
        response = self._get(
            DOCUMENT_URL.format(pk=self.pending_application.pk), self.employee
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])
        self.assertEqual(response.data["status"], ApprovedLeaveDocument.Status.FAILED)
        self.assertEqual(response.data["download_url"], "")

    def test_the_read_is_get_only(self):
        client = APIClient()
        client.force_authenticate(user=self.employee)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)(self.ready_url, {})
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_signing_failure_degrades_the_payload_instead_of_500ing(self):
        """A storage misconfiguration must not take the read endpoint down.

        The signed URL is derived from the document row, so when it cannot be
        minted the row is still readable. ``available`` goes false and no URL is
        returned: the alternative is serving the render-time URL, which has since
        expired and would hand the employee a dead "Open" button.
        """
        client = APIClient()
        client.force_authenticate(user=self.employee)
        for error in (
            ValueError("SUPABASE_URL must be the bare project URL"),
            StorageApiError("Object not found", code="404", status=404),
        ):
            with self.subTest(error=type(error).__name__):
                with mock.patch(
                    "leave.services.storage.signed_document_url", side_effect=error
                ):
                    with self.assertLogs("documents.views", level="ERROR"):
                        response = client.get(self.ready_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertFalse(response.data["available"])
                self.assertEqual(response.data["download_url"], "")
                # The document itself is unchanged and still reported as ready;
                # only the URL is withheld.
                self.assertEqual(response.data["status"], ApprovedLeaveDocument.Status.READY)
                self.assertEqual(response.data["file_name"], self.document.file_name)


class ReadyDocumentImmutabilityTests(TestCase):
    """A ready document is sealed (D2)."""

    def setUp(self):
        self.employee = make_user(User.Role.EMPLOYEE, "sealed_employee")
        self.application = approved_application(self.employee)
        self.document = ApprovedLeaveDocument.objects.create(
            application=self.application,
            status=ApprovedLeaveDocument.Status.READY,
            file_path=f"approved/{self.application.pk}/approved-leave.pdf",
        )

    def test_a_ready_document_cannot_be_mutated(self):
        with self.assertRaises(ApprovedLeaveDocumentLockedError):
            self.document.file_path = "somewhere/else.pdf"
            self.document.save()

    def test_a_ready_document_cannot_be_deleted(self):
        with self.assertRaises(ApprovedLeaveDocumentLockedError):
            self.document.delete()

    def test_the_queryset_refuses_to_delete_a_ready_document(self):
        with self.assertRaises(ApprovedLeaveDocumentLockedError):
            ApprovedLeaveDocument.objects.all().delete()

    def test_a_pending_document_can_still_be_failed(self):
        pending = ApprovedLeaveDocument.objects.create(
            application=LeaveApplication.objects.create(
                employee=self.employee,
                leave_type_id=annual_leave_type().pk,
                start_date=date(2026, 11, 2),
                end_date=date(2026, 11, 3),
                working_days=2,
                status=LeaveApplication.Status.APPROVED,
                reference_number="LV-2026-000999",
            )
        )
        pending.mark_failed("storage unavailable")
        pending.refresh_from_db()
        self.assertEqual(pending.status, ApprovedLeaveDocument.Status.FAILED)
        self.assertIn("storage unavailable", pending.error_message)
