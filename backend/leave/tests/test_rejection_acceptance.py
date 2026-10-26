"""Accepting a rejection: the other exit from a rejected application.

A rejection is a decision the employee has to respond to. Resubmission is one
response; accepting the rejection is the other, and it closes the application
without pretending the rejection did not happen. These tests pin that contract:

* the row stays ``rejected`` but gains ``rejection_accepted_at``;
* accepting is owner-only, idempotent, and refused on anything not rejected;
* an accepted rejection is no longer editable, resubmittable, or document-
  editable;
* tracking reports the acceptance and stops offering resubmission;
* the dashboard stops listing it under "Needs Your Attention".
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.documents.services import DocumentNotEditableError, ensure_editable
from leave.services.dashboard import get_dashboard_data
from leave.services.resubmission import (
    NotAcceptableError,
    NotResubmittableError,
    ResubmissionNotFoundError,
    accept_rejection,
    resubmit_application,
)
from leave.services.submission import submit_application
from approvals.models import ApprovalDecision
from approvals.services import decide

from .stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user

User = get_user_model()

ACCEPT_URL = "/api/v1/leave-applications/{id}/accept-rejection/"
TRACKING_URL = "/api/v1/leave-applications/{id}/tracking/"
DETAIL_URL = "/api/v1/leave-applications/{id}/"


class RejectionAcceptanceBase(StubProviderMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.stub = self.use_stub()
        self.client = APIClient()
        self.owner = make_user(
            "accept.owner@luanar", first_name="Koga", last_name="Employee"
        )
        self.other = make_user(
            "accept.other@luanar", first_name="Orie", last_name="Other"
        )
        self.supervisor = make_user(
            "accept.supervisor@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "accept.hod@luanar", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "accept.registrar@luanar",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        self.stub.register_employee(self.owner)
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
        ):
            self.stub.workflow.register_approver(role, user)
        self.client.force_authenticate(user=self.owner)

    def make_rejected(self):
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            reason="Family visit",
        )
        app = submit_application(user=self.owner, application_id=app.pk)
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.REJECT,
            comment="Dates clash with another trip.",
            expected_version=1,
        )
        app.refresh_from_db()
        return app


class AcceptRejectionServiceTests(RejectionAcceptanceBase):
    def test_accepting_closes_the_rejection_without_changing_its_status(self):
        app = self.make_rejected()

        accepted = accept_rejection(user=self.owner, application_id=app.pk)

        self.assertEqual(accepted.status, LeaveApplication.Status.REJECTED)
        self.assertIsNotNone(accepted.rejection_accepted_at)
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=app.pk,
                action=AuditEntry.Action.APPLICATION_REJECTION_ACCEPTED,
            ).exists()
        )

    def test_accepting_twice_is_idempotent(self):
        app = self.make_rejected()
        first = accept_rejection(user=self.owner, application_id=app.pk)
        stamp = first.rejection_accepted_at

        second = accept_rejection(user=self.owner, application_id=app.pk)

        self.assertEqual(second.rejection_accepted_at, stamp)
        self.assertEqual(
            AuditEntry.objects.filter(
                target_id=app.pk,
                action=AuditEntry.Action.APPLICATION_REJECTION_ACCEPTED,
            ).count(),
            1,
        )

    def test_a_foreign_application_is_not_found(self):
        app = self.make_rejected()

        with self.assertRaises(ResubmissionNotFoundError):
            accept_rejection(user=self.other, application_id=app.pk)

    def test_a_draft_has_no_rejection_to_accept(self):
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=2),
            reason="Family visit",
        )

        with self.assertRaises(NotAcceptableError):
            accept_rejection(user=self.owner, application_id=app.pk)

    def test_an_accepted_rejection_cannot_be_resubmitted(self):
        app = self.make_rejected()
        accept_rejection(user=self.owner, application_id=app.pk)

        with self.assertRaises(NotResubmittableError):
            resubmit_application(user=self.owner, application_id=app.pk)

    def test_an_accepted_rejection_is_not_document_editable(self):
        app = self.make_rejected()
        accept_rejection(user=self.owner, application_id=app.pk)
        app.refresh_from_db()

        with self.assertRaises(DocumentNotEditableError):
            ensure_editable(app)

    def test_the_tracking_payload_reports_the_acceptance(self):
        app = self.make_rejected()
        accept_rejection(user=self.owner, application_id=app.pk)

        response = self.client.get(TRACKING_URL.format(id=app.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["rejection"]["accepted_at"])
        self.assertFalse(response.data["resubmission"]["can_resubmit"])
        self.assertIsNone(response.data["resubmission"]["returns_to_stage"])

    def test_an_open_rejection_is_still_resubmittable_and_visible(self):
        app = self.make_rejected()

        response = self.client.get(TRACKING_URL.format(id=app.pk))

        self.assertIsNone(response.data["rejection"]["accepted_at"])
        self.assertTrue(response.data["resubmission"]["can_resubmit"])
        attention = [row["id"] for row in get_dashboard_data(self.owner)["needs_attention"]]
        self.assertIn(str(app.pk), attention)

    def test_an_accepted_rejection_leaves_needs_attention(self):
        app = self.make_rejected()
        accept_rejection(user=self.owner, application_id=app.pk)

        attention = [row["id"] for row in get_dashboard_data(self.owner)["needs_attention"]]

        self.assertNotIn(str(app.pk), attention)


class AcceptRejectionEndpointTests(RejectionAcceptanceBase):
    def test_accepting_returns_the_recorded_timestamp(self):
        app = self.make_rejected()

        response = self.client.post(ACCEPT_URL.format(id=app.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "rejected")
        self.assertIsNotNone(response.data["rejection_accepted_at"])
        app.refresh_from_db()
        self.assertIsNotNone(app.rejection_accepted_at)

    def test_accepting_a_non_rejected_application_is_a_conflict(self):
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=2),
            reason="Family visit",
        )

        response = self.client.post(ACCEPT_URL.format(id=app.pk))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "NOT_REJECTED")

    def test_a_foreign_application_is_not_found(self):
        app = self.make_rejected()
        self.client.force_authenticate(user=self.other)

        response = self.client.post(ACCEPT_URL.format(id=app.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_callers_are_refused(self):
        app = self.make_rejected()
        self.client.force_authenticate(user=None)

        response = self.client.post(ACCEPT_URL.format(id=app.pk))

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_an_accepted_rejection_cannot_be_edited(self):
        app = self.make_rejected()
        self.client.post(ACCEPT_URL.format(id=app.pk))

        response = self.client.patch(
            DETAIL_URL.format(id=app.pk), {"reason": "Changed"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        app.refresh_from_db()
        self.assertEqual(app.reason, "Family visit")

    def test_the_detail_payload_carries_the_acceptance(self):
        app = self.make_rejected()
        self.client.post(ACCEPT_URL.format(id=app.pk))

        response = self.client.get(DETAIL_URL.format(id=app.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["rejection_accepted_at"])
