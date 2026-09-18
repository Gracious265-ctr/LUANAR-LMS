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