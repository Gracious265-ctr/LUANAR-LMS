"""Endpoint tests for the Unit 15 tracking API (GET /api/v1/leave-applications/{id}/tracking/).

Ownership and gating:
- owner         -> 200 with the full Section 1 payload
- other employee -> 404 (never 403)
- HR/approver   -> 404 (never 403)
- anonymous     -> 401
- draft         -> 409 ``application_not_submitted``
- unknown id    -> 404
- non-GET       -> 405
- the whole owner request runs in a bounded number of queries

Since Unit 21 the endpoint runs on the real ``DatabaseTrackingProvider``, whose
payload derives from the ``ApplicationStage``/``ApprovalDecision``/audit rows
created by the real submission, decision and resubmission services. The
scenario tests therefore build that state through the services rather than
pre-baked fixtures.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveApplication, SupportingDocument
from leave.services.resubmission import resubmit_application
from leave.services.submission import submit_application
from approvals.models import ApprovalDecision
from workflows.testing import create_user_with_role
from approvals.services import decide

from .stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user

User = get_user_model()

TRACKING_URL = "/api/v1/leave-applications/{id}/tracking/"


class TrackingEndpointTests(StubProviderMixin, TestCase):
    """Shared helpers: owner + other-user + draft/app factories."""

    def setUp(self):
        super().setUp()
        self.stub = self.use_stub()
        self.client = APIClient()
        self.owner = make_user(
            "track.owner@luanar", first_name="Ken", last_name="Employee"
        )
        self.other = make_user(
            "track.other@luanar", first_name="Orie", last_name="Other"
        )
        self.supervisor = make_user(
            "track.supervisor@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "track.hod@luanar", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "track.registrar@luanar",
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

    def make_submitted(self):
        """A real submitted application on the stub's 4-stage chain."""
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            reason="Family visit",
        )
        return submit_application(user=self.owner, application_id=app.pk)

    def approve(self, app, actor):
        decide(
            application_id=app.pk,
            actor=actor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )

    @staticmethod
    def z(value):
        if not value:
            return None
        return value.isoformat().replace("+00:00", "Z")


class TrackingOwnershipTests(TrackingEndpointTests):
    def test_owner_gets_200_with_full_payload(self):
        app = self.make_submitted()
        response = self.client.get(self.url(app.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data["application"]["id"], str(app.id))
        self.assertEqual(data["application"]["reference_number"], app.reference_number)
        self.assertEqual(data["application"]["leave_type"]["name"], "Annual Leave")
        self.assertEqual(
            data["application"]["start_date"], EARLIEST_ANNUAL_START.isoformat()
        )
        self.assertEqual(
            data["application"]["end_date"],
            (EARLIEST_ANNUAL_START + timedelta(days=3)).isoformat(),
        )
        self.assertGreaterEqual(data["application"]["working_days"], 1)
        self.assertEqual(
            data["application"]["submitted_at"], self.z(app.submitted_at)
        )

        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["approved_at"])
        self.assertIsNotNone(data["current_stage"])
        self.assertEqual(len(data["stages"]), 4)
        self.assertGreaterEqual(len(data["events"]), 1)
        self.assertIsNone(data["rejection"])
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
        supervisor = create_user_with_role(
            username="supervisor@test.luanar",
            password="testpass123",
            role="supervisor",
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

    def test_owner_request_runs_a_bounded_number_of_queries(self):
        # 12, not the 11 the pre-section display needed: one query reads the
        # open stage's eligibility snapshot, which is where a section's authority
        # lives. It is fetched once for the whole chain rather than per stage, so
        # the bound stays flat as chains grow.
        app = self.make_submitted()
        with self.assertNumQueries(12):
            response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_documents_block_returns_active_rows(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        app = self.make_app()
        SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/abcd/active.pdf",
            file_url="stale://active",
            file_name="active.pdf",
            file_size=100,
            content_type="application/pdf",
        )
        retired = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/abcd/old.pdf",
            file_url="stale://old",
            file_name="old.pdf",
            file_size=100,
            content_type="application/pdf",
        )
        retired.retire(self.owner, reason=SupportingDocument.RetireReason.REPLACED)

        response = self.client.get(self.url(app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        docs = response.data["documents"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["file_name"], "active.pdf")
        self.assertEqual(
            docs[0]["id"], str(SupportingDocument.objects.get(file_name="active.pdf").id)
        )
        self.assertNotIn("file_path", docs[0])

    def test_current_stage_is_serialized_passthrough(self):
        app = self.make_submitted()
        response = self.client.get(self.url(app.id))
        current = response.data["current_stage"]
        self.assertEqual(current["order"], 1)
        self.assertEqual(current["role"], "supervisor")
        self.assertEqual(current["role_label"], "Supervisor")
        self.assertEqual(current["approver_name"], "Sana Supervisor")
        self.assertIs(current["is_delegate"], False)
        self.assertIsNone(current["on_behalf_of"])
        self.assertEqual(current["assigned_at"], self.z(app.submitted_at))

    def test_events_are_sorted_newest_first(self):
        app = self.make_submitted()
        self.approve(app, self.supervisor)
        response = self.client.get(self.url(app.id))
        occurred = [event["occurred_at"] for event in response.data["events"]]
        self.assertEqual(occurred, sorted(occurred, reverse=True))
        self.assertIsInstance(response.data["events"][0]["actor"], dict)

    def test_rejection_payload_uses_reason_key(self):
        app = self.make_submitted()
        self.approve(app, self.supervisor)
        decide(
            application_id=app.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.REJECT,
            comment="Unsupported dates",
            expected_version=1,
        )
        response = self.client.get(self.url(app.id))
        rejection = response.data["rejection"]
        self.assertEqual(rejection["stage_order"], 2)
        self.assertEqual(rejection["role_label"], "Head of Department")
        self.assertEqual(rejection["approver_name"], "Hady Od")
        self.assertEqual(rejection["reason"], "Unsupported dates")
        self.assertIn("reason", rejection)
        self.assertNotIn("comment", rejection)

    def test_outcomes_are_null_after_resubmission(self):
        app = self.make_submitted()
        self.approve(app, self.supervisor)
        decide(
            application_id=app.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.REJECT,
            comment="Duplicate.",
            expected_version=1,
        )
        resubmit_application(user=self.owner, application_id=app.pk)
        response = self.client.get(self.url(app.id))
        self.assertIsNone(response.data["rejection"])
        self.assertEqual(response.data["resubmission"]["count"], 1)
        audit_row = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=str(app.pk),
            action=AuditEntry.Action.APPLICATION_RESUBMITTED,
        )
        self.assertEqual(
            response.data["resubmission"]["last_resubmitted_at"],
            self.z(audit_row.created_at),
        )
        self.assertFalse(response.data["resubmission"]["can_resubmit"])
