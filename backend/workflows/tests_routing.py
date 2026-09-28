"""Unit 21 — acting-approver routing tests (D2/D3/D8).

Covers the ``LeaveApplication.current_approver`` spine: approve advances it to
the next stage's configured approver, reject/correction leave it in place;
delegation redirects the acting approver at query time without touching the
spine (delegate sees and decides, original does not while active, fallback once
ended, never cascaded); reassignment moves the spine explicitly without
mutating the stage snapshot. Also the workflow gate: a submission with no
applicable workflow reaches the API as ``workflow_unavailable`` (422), and a
misconfigured workflow inside ``assign_workflow`` never 500s.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from leave.models import LeaveApplication
from leave.services.submission import submit_application
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    StubRulesProvider,
    TODAY,
    make_user,
)
from users.models import EmployeeProfile

from .models import ApprovalDecision, ApplicationStage, Delegation, Reassignment
from .policies import get_decision_authority
from .services import (
    acting_approver_id,
    acting_approver_identity,
    acting_approver_map,
    active_delegation_for,
    decide,
    reassign_application,
)

User = get_user_model()

ANNUAL = {
    "leave_type_id": 1,
    "start_date": EARLIEST_ANNUAL_START,
    "reason": "Family visit",
}


class RoutingBase(StubProviderMixin, APITestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.employee = make_user(
            "emp@routing", first_name="Ken", last_name="Employee"
        )
        self.supervisor = make_user(
            "sup@routing",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "hod@routing", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "reg@routing",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        self.dean = make_user(
            "dean@routing", role="dean", first_name="Dena", last_name="Dean"
        )
        self.dvc = make_user(
            "dvc@routing", role="dvc", first_name="Din", last_name="Vc"
        )
        self.hr = make_user(
            "hr@routing", role=User.Role.HR, first_name="Hry", last_name="Hr"
        )
        self.stub.register_employee(self.employee)
        EmployeeProfile.objects.create(
            user=self.employee,
            designation="Junior Officer",
            department="Administration",
            grade="B",
        )
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
            ("dvc", self.dvc),
        ):
            self.stub.workflow.register_approver(role, user)

    def make_submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def approve(self, app, actor):
        decide(
            application_id=app.pk,
            actor=actor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )

    def delegation_for(self, approver, delegate):
        today = timezone.localdate()
        return Delegation.objects.create(
            approver=approver,
            delegate=delegate,
            starts_on=today - timedelta(days=1),
            ends_on=today + timedelta(days=5),
            status=Delegation.Status.APPROVED,
            requested_by=approver,
            decided_by=self.hr,
            decision_reason="Coverage",
        )

    def pending_ids(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return [
            row["id"]
            for row in client.get("/api/v1/approvals/?tab=pending").data["results"]
        ]


class SpineAdvanceTests(RoutingBase):
    def test_approve_advances_current_approver_to_next_stage(self):
        app = self.make_submitted()
        self.assertEqual(app.current_approver_id, self.supervisor.id)
        self.assertEqual(app.current_stage.stage_order, 1)
        self.approve(app, self.supervisor)
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_approver_id, self.hod.id)

    def test_reject_keeps_spine_at_the_deciding_stage(self):
        app = self.make_submitted()
        self.approve(app, self.supervisor)
        decide(
            application_id=app.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.REJECT,
            comment="Unsupported dates",
            expected_version=1,
        )
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_approver_id, self.hod.id)

    def test_correction_keeps_spine_at_the_deciding_stage(self):
        app = self.make_submitted()
        self.approve(app, self.supervisor)
        self.approve(app, self.hod)
        decide(
            application_id=app.pk,
            actor=self.registrar,
            action=ApprovalDecision.Action.RETURN_FOR_CORRECTION,
            comment="Fix the dates",
            expected_version=1,
        )
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 3)
        self.assertEqual(app.current_approver_id, self.registrar.id)


class DelegationRoutingTests(RoutingBase):
    def test_delegate_is_the_acting_approver_while_active(self):
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        self.assertEqual(active_delegation_for(self.supervisor).delegate_id, self.dean.id)
        self.assertEqual(acting_approver_id(app), self.dean.id)

    def test_pending_list_shows_delegate_not_original(self):
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        self.assertIn(str(app.pk), self.pending_ids(self.dean))
        self.assertNotIn(str(app.pk), self.pending_ids(self.supervisor))

    def test_authority_grants_delegate_and_denies_original(self):
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        self.assertTrue(get_decision_authority(self.dean, app).can_decide)
        self.assertFalse(get_decision_authority(self.supervisor, app).can_decide)

    def test_delegated_decision_records_the_delegate(self):
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        self.approve(app, self.dean)
        decision = ApprovalDecision.objects.get(application=app)
        self.assertEqual(decision.approver_id, self.dean.id)
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.hod.id)

    def test_spine_falls_back_when_delegation_ends(self):
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        today = timezone.localdate()
        Delegation.objects.filter(approver=self.supervisor).update(ends_on=today - timedelta(days=1))
        self.assertEqual(active_delegation_for(self.supervisor), None)
        self.assertEqual(acting_approver_id(app), self.supervisor.id)
        self.assertNotIn(str(app.pk), self.pending_ids(self.dean))
        self.assertIn(str(app.pk), self.pending_ids(self.supervisor))

    def test_delegation_is_never_cascaded(self):
        self.delegation_for(self.supervisor, self.dean)
        self.delegation_for(self.dean, self.dvc)
        app = self.make_submitted()
        self.assertEqual(acting_approver_id(app), self.dean.id)
        self.assertNotIn(str(app.pk), self.pending_ids(self.dvc))


class ReassignmentRoutingTests(RoutingBase):
    def test_reassigned_approver_sees_and_decides_without_stage_mutation(self):
        app = self.make_submitted()
        history = reassign_application(
            application=app,
            to_approver=self.dean,
            actor=self.hr,
            reason="Emergency cover",
        )
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.dean.id)
        stage = app.current_stage
        self.assertEqual(stage.stage_order, 1)
        self.assertEqual(stage.status, ApplicationStage.Status.PENDING)
        self.assertEqual(stage.assigned_approver_id, self.supervisor.id)
        self.assertEqual(history.from_approver_id, self.supervisor.id)
        self.assertEqual(history.to_approver_id, self.dean.id)
        self.assertIn(str(app.pk), self.pending_ids(self.dean))
        self.assertNotIn(str(app.pk), self.pending_ids(self.supervisor))
        self.assertTrue(get_decision_authority(self.dean, app).can_decide)
        self.approve(app, self.dean)
        decision = ApprovalDecision.objects.get(application=app)
        self.assertEqual(decision.approver_id, self.dean.id)
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)

    def test_reassigning_away_from_a_delegated_approver_hands_over_cleanly(self):
        """The old cover no longer applies once the spine has moved.

        Reassignment is a spine write and delegation is a query-time overlay, so
        pointing the spine at someone else takes the application out of the
        original approver's delegation entirely.
        """
        self.delegation_for(self.supervisor, self.dean)
        app = self.make_submitted()
        self.assertEqual(acting_approver_id(app), self.dean.id)

        reassign_application(
            application=app, to_approver=self.hod, actor=self.hr, reason="Escalate"
        )
        app.refresh_from_db()

        self.assertEqual(app.current_approver_id, self.hod.id)
        self.assertEqual(acting_approver_id(app), self.hod.id)
        self.assertIn(str(app.pk), self.pending_ids(self.hod))
        self.assertNotIn(str(app.pk), self.pending_ids(self.dean))
        self.assertNotIn(str(app.pk), self.pending_ids(self.supervisor))

    def test_reassigning_to_an_away_approver_leaves_their_delegate_acting(self):
        """Documented consequence, not an accident: the overlay wins.

        Reassigning to an approver with active cover moves the spine to them, but
        ``acting_approver_id`` then hands the application to *their* delegate.
        The intervention is recorded and the approver owns it on paper while
        someone else acts — which is why the pending queue reports the acting
        approver alongside the responsible one.
        """
        self.delegation_for(self.hod, self.dvc)
        app = self.make_submitted()

        reassign_application(
            application=app, to_approver=self.hod, actor=self.hr, reason="Escalate"
        )
        app.refresh_from_db()

        self.assertEqual(app.current_approver_id, self.hod.id)
        self.assertEqual(acting_approver_id(app), self.dvc.id)
        self.assertTrue(get_decision_authority(self.dvc, app).can_decide)
        self.assertFalse(get_decision_authority(self.hod, app).can_decide)
        self.assertIn(str(app.pk), self.pending_ids(self.dvc))
        self.assertNotIn(str(app.pk), self.pending_ids(self.hod))

    def test_the_acting_approver_map_matches_the_single_row_resolver(self):
        """The bulk resolver the queue uses must agree with ``acting_approver_id``."""
        self.delegation_for(self.supervisor, self.dean)
        delegated = self.make_submitted()
        # Plain rows: the resolver only reads the spine, and the stub entitlement
        # balance will not fund a second real submission. ``registrar`` has no
        # cover, so it stands in for the undelegated case.
        covered = self._pending_row(self.supervisor)
        plain = self._pending_row(self.registrar)
        unassigned = self._pending_row(None)
        rows = [delegated, covered, plain, unassigned]

        resolved = acting_approver_map(rows)

        self.assertEqual(
            resolved[delegated.pk], (self.dean.id, self.dean.get_full_name())
        )
        # The same cover applies to any application the supervisor holds.
        self.assertEqual(
            resolved[covered.pk], (self.dean.id, self.dean.get_full_name())
        )
        self.assertEqual(
            resolved[plain.pk], (self.registrar.id, self.registrar.get_full_name())
        )
        self.assertNotIn(unassigned.pk, resolved)
        for app in rows:
            self.assertEqual(
                acting_approver_identity(app)[0], acting_approver_id(app)
            )

    def _pending_row(self, approver):
        return LeaveApplication.objects.create(
            employee=self.employee,
            current_approver=approver,
            status=LeaveApplication.Status.SUBMITTED,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )


class WorkflowGateTests(StubProviderMixin, TestCase):
    """Invariant 12.7: ``workflow_unavailable`` reaches the API as 422."""

    def setUp(self):
        self.stub = StubRulesProvider()
        self.client = APIClient()
        self.user = make_user("gate@routing")
        self.stub.register_employee(self.user)
        EmployeeProfile.objects.create(
            user=self.user,
            designation="Junior Officer",
            department="Administration",
            category="administration",
            grade="B",
        )
        self.client.force_authenticate(user=self.user)

    def draft(self):
        return LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            reason="Annual leave",
        )

    def patch_rules(self):
        patchers = [
            mock.patch(
                "leave.validation.pipeline.get_provider", return_value=self.stub
            ),
            mock.patch(
                "leave.validation.pipeline.get_today", return_value=TODAY
            ),
            mock.patch("leave.providers.get_provider", return_value=self.stub),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_no_applicable_workflow_is_422_workflow_unavailable(self):
        self.patch_rules()
        app = self.draft()
        response = self.client.post(
            f"/api/v1/leave-applications/{app.pk}/submit/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_FAILED")
        codes = {e["code"] for e in response.data["errors"]}
        self.assertIn("workflow_unavailable", codes)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)

    def test_misconfigured_workflow_never_500s(self):
        from .providers import WorkflowConfigError

        class BrokenProvider:
            def get_stage_definitions(self, application):
                raise WorkflowConfigError("Stage role is invalid.")

            def get_workflow_member_user_ids(self, application):
                return []

            def get_cancellation_stages(self, application):
                return []

        self.patch_rules()
        patchers = [
            mock.patch(
                "leave.services.workflow_gate.check_workflow_ready",
                return_value=True,
            ),
            mock.patch(
                "workflows.providers.get_workflow_provider",
                return_value=BrokenProvider(),
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        app = self.draft()
        response = self.client.post(
            f"/api/v1/leave-applications/{app.pk}/submit/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        codes = {e["code"] for e in response.data["errors"]}
        self.assertIn("workflow_unavailable", codes)