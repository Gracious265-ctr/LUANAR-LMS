"""Endpoint tests for ``/api/v1/leave/validate/`` and ``.../submit/`` (Unit 14)."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication

from .stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_user,
    register_chain_approvers,
)


class ValidationEndpointTests(StubProviderMixin, TestCase):
    url = "/api/v1/leave/validate/"

    def setUp(self):
        self.stub = self.use_stub()
        self.client = APIClient()
        self.user = make_user()
        self.stub.register_employee(self.user)
        self.client.force_authenticate(user=self.user)

    def valid_payload(self, **overrides):
        payload = {
            "leave_type_id": 1,
            "start_date": "2026-09-28",
            "end_date": "2026-10-02",
        }
        payload.update(overrides)
        return payload

    def test_requires_authentication(self):
        client = APIClient()
        response = client.post(self.url, self.valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_application_always_returns_200(self):
        response = self.client.post(self.url, self.valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["working_days"], 5)
        self.assertEqual(response.data["calendar_days"], 5)
        self.assertEqual(response.data["financial_year"], "2026-27")
        self.assertEqual(response.data["available_balance"], "24")
        self.assertEqual(response.data["balance_after_if_approved"], "19")
        self.assertIn("documents", response.data["skipped_checks"])

    def test_invalid_application_returns_all_errors_at_200(self):
        response = self.client.post(
            self.url,
            self.valid_payload(
                start_date="2026-09-21",
                end_date="2026-09-24",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        codes = {e["code"] for e in response.data["errors"]}
        self.assertIn("START_ON_SUBMISSION_DATE", codes)
        self.assertIn("MIN_NOTICE_NOT_MET", codes)

    def test_missing_fields_are_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unowned_draft_id_is_404(self):
        other = make_user(username="other@test.luanar")
        self.stub.register_employee(other)
        draft = LeaveApplication.objects.create(
            employee=other,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Someone else's draft",
        )
        response = self.client.post(
            self.url,
            self.valid_payload(draft_id=str(draft.id)),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owned_draft_id_attaches_documents_and_reason_checks(self):
        draft = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=2,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Maternity leave",
        )
        response = self.client.post(
            self.url,
            self.valid_payload(leave_type_id=2, draft_id=str(draft.id)),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # With a draft attached the document/reason checks now run, not skip.
        self.assertNotIn("documents", response.data["skipped_checks"])
        self.assertNotIn("reason", response.data["skipped_checks"])
        codes = {e["code"] for e in response.data["errors"]}
        self.assertEqual(codes, {"DOCUMENT_REQUIRED"})


class SubmitEndpointTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.client = APIClient()
        self.user = make_user()
        self.stub.register_employee(self.user)
        register_chain_approvers(self.stub)
        self.client.force_authenticate(user=self.user)

    def draft(self, **kwargs):
        defaults = dict(
            employee=self.user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )
        defaults.update(kwargs)
        return LeaveApplication.objects.create(**defaults)

    def url(self, app_id):
        return f"/api/v1/leave-applications/{app_id}/submit/"

    def test_requires_authentication(self):
        app = self.draft()
        client = APIClient()
        response = client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_success_payload(self):
        app = self.draft()
        response = self.client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(body["id"], str(app.id))
        self.assertEqual(body["reference_number"], "LV-2026-27-000001")
        self.assertEqual(body["status"], "submitted")
        self.assertIsNotNone(body["submitted_at"])
        self.assertEqual(body["working_days"], 5)
        self.assertEqual(body["calendar_days"], 5)
        self.assertEqual(body["leave_type"]["id"], 1)
        self.assertEqual(body["leave_type"]["code"], "annual")
        self.assertEqual(body["start_date"], "2026-09-28")
        self.assertEqual(body["end_date"], "2026-10-02")

    def test_duplicate_submission_is_409_with_reference(self):
        app = self.draft(
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LV-2026-27-000755",
        )
        response = self.client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ALREADY_SUBMITTED")
        self.assertEqual(
            response.data["reference_number"], "LV-2026-27-000755"
        )

    def test_missing_or_unowned_application_is_404(self):
        other = make_user(username="other@test.luanar")
        self.stub.register_employee(other)
        app = self.draft(employee=other)
        response = self.client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_draft_application_is_409(self):
        app = self.draft(status="pending")
        response = self.client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "APPLICATION_NOT_SUBMITTABLE")

    def test_validation_failure_is_422_with_errors(self):
        self.stub.set_balance(self.user.id, "2026-27", Decimal("0"))
        app = self.draft()
        response = self.client.post(self.url(app.id), format="json")
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_FAILED")
        codes = {e["code"] for e in response.data["errors"]}
        self.assertIn("INSUFFICIENT_BALANCE", codes)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)

    def test_consecutive_submissions_get_sequential_references(self):
        app_a = self.draft()
        app_b = self.draft(
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
            reason="Second leave",
        )
        ref_a = self.client.post(self.url(app_a.id), format="json").data[
            "reference_number"
        ]
        ref_b = self.client.post(self.url(app_b.id), format="json").data[
            "reference_number"
        ]
        self.assertEqual(ref_a, "LV-2026-27-000001")
        self.assertEqual(ref_b, "LV-2026-27-000002")