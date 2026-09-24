"""Endpoint tests for the Unit 15 tracking API (GET /api/v1/leave-applications/{id}/tracking/).

Ownership and gating:
- owner         -> 200 with the full Section 1 payload
- other employee -> 404 (never 403)
- HR/approver   -> 404 (never 403)
- anonymous     -> 401
- draft         -> 409 ``application_not_submitted``
- unknown id    -> 404
- non-GET       -> 405
- exactly two queries for the whole request (one for the application, one for
  the latest cancellation request; the fixture provider does no DB access)
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication

from .stubs import make_user

User = get_user_model()

TRACKING_URL = "/api/v1/leave-applications/{id}/tracking/"


class TrackingEndpointTests(TestCase):
    """Shared helpers: owner + other-user + draft/app factories."""

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user()
        self.other = make_user(username="other@test.luanar")
        self.client.force_authenticate(user=self.owner)

    def url(self, app_id):
        return TRACKING_URL.format(id=app_id)

    def make_app(self, *, owner=None, status_=LeaveApplication.Status.SUBMITTED, **kwargs):
        reference = kwargs.pop("reference_number", "LV-2026-27-900001")
        return LeaveApplication.objects.create(
            employee=owner or self.owner,
            leave_type_id=1,
            start_date="2026-11-02",
            end_date="2026-11-06",
            working_days=5,
            calendar_days=5,
            financial_year_label="2026-27",
            status=status_,
            reference_number=reference,
            submitted_at="2026-10-12T07:15:03Z",
            rules_snapshot={
                "leave_type": {"id": 1, "name": "Annual Leave"}
            },
            **kwargs,
        )


class TrackingOwnershipTests(TrackingEndpointTests):
    def test_owner_gets_200_with_full_payload(self):
        app = self.make_app()
        response = self.client.get(self.url(app.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data["application"]["id"], str(app.id))
        self.assertEqual(data["application"]["reference_number"], "LV-2026-27-900001")
        self.assertEqual(data["application"]["leave_type"]["name"], "Annual Leave")
        self.assertEqual(data["application"]["start_date"], "2026-11-02")
        self.assertEqual(data["application"]["end_date"], "2026-11-06")
        self.assertEqual(data["application"]["working_days"], 5)
        self.assertEqual(data["application"]["submitted_at"], "2026-10-12T07:15:03Z")

        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["approved_at"])
        self.assertIsNotNone(data["current_stage"])
        self.assertEqual(len(data["stages"]), 4)
        self.assertGreaterEqual(len(data["events"]), 1)
        self.assertIsNone(data["rejection"])
        self.assertIsNone(data["correction"])
        self.assertEqual(data["resubmission"]["count"], 0)
        self.assertFalse(data["resubmission"]["can_resubmit"])

    def test_other_employee_gets_404(self):
        app = self.make_app()
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_user_gets_404_not_403(self):
        hr = User.objects.create_user(
            username="hr@test.luanar",
            password="testpass123",
            role=User.Role.HR,
        )
        app = self.make_app()
        self.client.force_authenticate(user=hr)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_supervisor_approver_gets_404(self):
        supervisor = User.objects.create_user(
            username="supervisor@test.luanar",
            password="testpass123",
            role=User.Role.SUPERVISOR,
        )
        app = self.make_app()
        self.client.force_authenticate(user=supervisor)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_gets_401(self):
        app = self.make_app()
        client = APIClient()
        response = client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_id_gets_404(self):
        import uuid

        response = self.client.get(self.url(uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_draft_gets_409_application_not_submitted(self):
        app = self.make_app(status_=LeaveApplication.Status.DRAFT)
        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "application_not_submitted")

    def test_non_get_methods_are_405(self):
        app = self.make_app()
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(self.url(app.id))
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_only_one_query_for_owner_request(self):
        app = self.make_app()
        with self.assertNumQueries(2):
            response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_current_stage_is_serialized_passthrough(self):
        app = self.make_app()
        response = self.client.get(self.url(app.id))
        current = response.data["current_stage"]
        self.assertEqual(current["order"], 1)
        self.assertEqual(current["role_label"], "Supervisor")
        self.assertEqual(current["approver_name"], "Mr. Chikondi Banda")
        self.assertEqual(current["assigned_at"], "2026-10-12T08:32:11Z")

    def test_events_are_sorted_newest_first(self):
        app = self.make_app(reference_number="LV-2026-27-900005")
        response = self.client.get(self.url(app.id))
        occurred = [event["occurred_at"] for event in response.data["events"]]
        self.assertEqual(occurred, sorted(occurred, reverse=True))
        self.assertIsInstance(response.data["events"][0]["actor"], dict)

    def test_rejection_payload_uses_reason_key(self):
        app = self.make_app(reference_number="LV-2026-27-900005")
        response = self.client.get(self.url(app.id))
        rejection = response.data["rejection"]
        self.assertEqual(rejection["stage_order"], 2)
        self.assertEqual(rejection["role_label"], "Dean")
        self.assertEqual(rejection["approver_name"], "Dr. Anne Banda")
        self.assertIn("reason", rejection)
        self.assertNotIn("comment", rejection)
        self.assertIsNone(response.data["correction"])

    def test_correction_payload_uses_comment_key(self):
        app = self.make_app(reference_number="LV-2026-27-900006")
        response = self.client.get(self.url(app.id))
        correction = response.data["correction"]
        self.assertEqual(correction["stage_order"], 3)
        self.assertEqual(correction["role_label"], "Registrar")
        self.assertIn("comment", correction)
        self.assertNotIn("reason", correction)
        self.assertIsNone(response.data["rejection"])

    def test_outcomes_are_null_after_resubmission(self):
        app = self.make_app(reference_number="LV-2026-27-900007")
        response = self.client.get(self.url(app.id))
        self.assertIsNone(response.data["rejection"])
        self.assertIsNone(response.data["correction"])
        self.assertEqual(response.data["resubmission"]["count"], 1)
        self.assertEqual(
            response.data["resubmission"]["last_resubmitted_at"],
            "2026-10-19T09:00:00Z",
        )
        self.assertFalse(response.data["resubmission"]["can_resubmit"])