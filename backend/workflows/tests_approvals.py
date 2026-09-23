"""Unit 16 tests: approval review and decision.

Covers the decision service and its transition table, comment rules, authority
and visibility policies, the immutable decision records (ORM helpers, admin and
DB constraints), optimistic concurrency, the approvals API (list/detail/
decision/documents), the workflow snapshot invariance, and the no-side-effect
contract.
"""

from datetime import date
from unittest import mock
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEvent
from leave.models import LeaveApplication, SupportingDocument
from leave.providers.base import LeaveBalanceUnavailableError
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_approver_chain,
    make_user,
)
from users.models import EmployeeProfile

from . import fixture_provider
from .approval import decide
from .assignment import assign_workflow
from .errors import DecisionValidationError, NotAllowed, StageChanged
from .events import ApprovalEvent, emit_approval_event
from .models import ApplicationStage, ApprovalDecision
from .policies import get_decision_authority, get_leave_history_scope, get_view_access


class ApprovalFixtureMixin(StubProviderMixin):
    """Submit employee applications routed by the real fixture provider."""

    def setUpApprovals(self):
        self.stub = self.use_stub()
        chain = make_approver_chain()
        self.supervisor = chain["supervisor"]
        self.hod = chain["hod"]
        self.dean = chain["dean"]
        self.registrar = chain["registrar"]
        self.dvc = chain["dvc"]

        # employee@test.luanar is category "administration" (fixture data) and
        # routes Supervisor-free: HOD -> Dean -> Registrar -> DVC.
        self.employee = make_user()
        self.stub.register_employee(self.employee)

        # academic@test.luanar carries an EmployeeProfile with category
        # "academic" so the fixture provider routes Supervisor -> HOD -> ...
        self.academic = make_user(username="academic@test.luanar")
        self.stub.register_employee(
            self.academic, grade="E", category="academic", gender="M"
        )
        self.set_profile(self.academic, department="Computer Science")
        # Applications share the DB, so submission date ranges must not overlap
        # (the provider rejects DUPLICATE_OVERLAP). The cursor hands out disjoint
        # five-working-day blocks per submit call.
        self._dates_cursor = None

    def submit(self, *, employee=None, start_date=None, end_date=None, **kwargs):
        employee = employee or self.employee
        from datetime import timedelta

        cursor = self._dates_cursor or EARLIEST_ANNUAL_START
        # Blocks must start on a working day (START_NOT_WORKING_DAY) and never
        # collide (DUPLICATE_OVERLAP); snap the shared cursor past weekends so
        # every auto-assigned block is a Mon-Fri five-day range.
        while cursor.weekday() >= 5:
            cursor += timedelta(days=1)
        if start_date is None:
            start = cursor
            end = cursor + timedelta(days=4)
        else:
            start = start_date
            end = end_date or start + timedelta(days=4)
        if end >= cursor:
            self._dates_cursor = end + timedelta(days=1)
            while self._dates_cursor.weekday() >= 5:
                self._dates_cursor += timedelta(days=1)
        defaults = dict(
            employee=employee,
            leave_type_id=1,
            start_date=start,
            end_date=end,
            reason="Annual leave",
        )
        defaults.update(kwargs)
        app = LeaveApplication.objects.create(**defaults)
        from leave.services.submission import submit_application

        submit_application(user=employee, application_id=app.id)
        app.refresh_from_db()
        return app

    def advance(self, app, *step_approvers):
        """Apply an approve decision through the given approvers."""
        last = None
        for approver in step_approvers:
            stage = app.current_stage
            last = decide(
                application_id=app.id,
                actor=approver,
                action="approve",
                comment="Approved",
                expected_stage_version=stage.version,
            )
            app.refresh_from_db()
        return last

    def set_profile(self, user, *, department="Computer Science",
                    category="academic", grade="G", designation="Lecturer"):
        return EmployeeProfile.objects.create(
            user=user,
            designation=designation,
            department=department,
            category=category,
            grade=grade,
            appointment_date=date(2020, 1, 1),
        )

    def update_profile(self, user, **fields):
        # Mutate through the cached instance (not a raw QuerySet.update) so the
        # user's ``employee_profile`` reverse cache stays coherent with the DB
        # (policies read the cached relation, e.g. for unit comparisons).
        profile = getattr(user, "employee_profile", None)
        if profile is None:
            return EmployeeProfile.objects.filter(user=user).update(**fields)
        for key, value in fields.items():
            setattr(profile, key, value)
        profile.save()
        return 1


class DecisionServiceTests(ApprovalFixtureMixin, TestCase):
    def setUp(self):
        self.setUpApprovals()

    def _stage(self, app, order):
        return ApplicationStage.objects.get(application=app, stage_order=order)

    def test_approve_advances_exactly_one_stage(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        self.assertEqual(stage1.role, "hod")
        self.assertEqual(app.status, LeaveApplication.Status.PENDING)

        decide(
            application_id=app.id,
            actor=self.hod,
            action="approve",
            comment="Looks good",
            expected_stage_version=stage1.version,
        )
        app.refresh_from_db()

        self.assertEqual(self._stage(app, 1).status, "approved")
        self.assertEqual(self._stage(app, 2).status, "pending")
        self.assertEqual(self._stage(app, 3).status, "waiting")
        self.assertEqual(self._stage(app, 4).status, "waiting")
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_stage.assigned_approver_id, self.dean.id)
        self.assertEqual(app.status, LeaveApplication.Status.PENDING)
        self.assertEqual(self._stage(app, 1).version, 2)
        self.assertEqual(self._stage(app, 2).version, 2)

    def test_final_approve_sets_application_approved(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar)
        final = self._stage(app, 4)
        self.assertTrue(final.is_final)
        decide(
            application_id=app.id,
            actor=self.dvc,
            action="approve",
            comment="",
            expected_stage_version=final.version,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(app.current_stage.stage_order, 4)
        self.assertEqual(self._stage(app, 4).status, "approved")

    def test_reject_stops_the_workflow(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        decide(
            application_id=app.id,
            actor=self.hod,
            action="reject",
            comment="Insufficient staffing",
            expected_stage_version=stage1.version,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(self._stage(app, 1).status, "rejected")
        for order in (2, 3, 4):
            self.assertEqual(self._stage(app, order).status, "waiting")
        self.assertEqual(app.current_stage.stage_order, 1)

    def test_return_sets_correction_required_and_keeps_current_stage(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        decide(
            application_id=app.id,
            actor=self.hod,
            action="return_for_correction",
            comment="Fix the dates",
            expected_stage_version=stage1.version,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CORRECTION_REQUIRED)
        self.assertEqual(self._stage(app, 1).status, "correction_requested")
        self.assertEqual(app.current_stage.stage_order, 1)

    def test_approve_with_blank_comment_succeeds(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        decide(
            application_id=app.id,
            actor=self.hod,
            action="approve",
            comment="",
            expected_stage_version=stage1.version,
        )
        decision = ApprovalDecision.objects.get(application=app)
        self.assertEqual(decision.comment, "")
        self.assertEqual(decision.action, "approve")
        self.assertEqual(decision.approver_name, self.hod.username)
        self.assertEqual(decision.role_label, "Head of Department")
        self.assertEqual(decision.submission_cycle, 1)

    def test_reject_requires_comment(self):
        for comment in ("", "   "):
            app = self.submit()
            stage1 = self._stage(app, 1)
            with self.assertRaises(DecisionValidationError) as ctx:
                decide(
                    application_id=app.id,
                    actor=self.hod,
                    action="reject",
                    comment=comment,
                    expected_stage_version=stage1.version,
                )
            self.assertEqual(ctx.exception.field, "comment")

    def test_return_requires_comment(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        with self.assertRaises(DecisionValidationError):
            decide(
                application_id=app.id,
                actor=self.hod,
                action="return_for_correction",
                comment="   ",
                expected_stage_version=stage1.version,
            )

    def test_comment_over_1000_characters_fails(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        with self.assertRaises(DecisionValidationError) as ctx:
            decide(
                application_id=app.id,
                actor=self.hod,
                action="approve",
                comment="x" * 1001,
                expected_stage_version=stage1.version,
            )
        self.assertEqual(ctx.exception.field, "comment")

    def test_invalid_action_fails(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        with self.assertRaises(DecisionValidationError) as ctx:
            decide(
                application_id=app.id,
                actor=self.hod,
                action="cancel",
                comment="nope",
                expected_stage_version=stage1.version,
            )
        self.assertEqual(ctx.exception.field, "action")

    def test_database_check_constraint_blocks_commentless_reject(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        with self.assertRaises(IntegrityError):
            ApprovalDecision.objects.create(
                application=app,
                stage=stage1,
                approver=self.hod,
                approver_name="x",
                role_label="Head of Department",
                action="reject",
                comment="",
            )

    def test_decisions_are_immutable_via_orm(self):
        app = self.submit()
        self.advance(app, self.hod)
        decision = ApprovalDecision.objects.get(application=app)
        with self.assertRaises(Exception) as ctx:
            decision.comment = "changed"
            decision.save()
        self.assertIn("immutable", str(ctx.exception).lower())
        with self.assertRaises(Exception):
            decision.delete()
        with self.assertRaises(Exception):
            ApprovalDecision.objects.filter(pk=decision.pk).update(action="reject")

    def test_sequential_integrity_no_skipping(self):
        app = self.submit()
        stage4 = self._stage(app, 4)
        with self.assertRaises(NotAllowed) as ctx:
            decide(
                application_id=app.id,
                actor=self.dvc,
                action="approve",
                comment="",
                expected_stage_version=stage4.version,
            )
        self.assertEqual(ctx.exception.reason, "not_current_stage")

    def test_stale_stage_version_returns_409_signal(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        with self.assertRaises(StageChanged):
            decide(
                application_id=app.id,
                actor=self.hod,
                action="approve",
                comment="",
                expected_stage_version=stage1.version - 1,
            )
        # A replay of the same request records only one decision.
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 0)

    def test_second_decision_by_same_approver_is_blocked(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        decide(
            application_id=app.id,
            actor=self.hod,
            action="approve",
            comment="",
            expected_stage_version=stage1.version,
        )
        app.refresh_from_db()
        with self.assertRaises(NotAllowed) as ctx:
            decide(
                application_id=app.id,
                actor=self.hod,
                action="approve",
                comment="",
                expected_stage_version=stage1.version + 1,
            )
        self.assertEqual(ctx.exception.reason, "already_decided")
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 1)

    def test_decision_authority_reasons(self):
        app = self.submit()
        # Non-assigned user.
        auth = get_decision_authority(self.employee, app)
        self.assertFalse(auth.can_decide)
        self.assertEqual(auth.reason, "not_current_stage")
        # Assigned approver.
        auth = get_decision_authority(self.hod, app)
        self.assertTrue(auth.can_decide)
        self.assertIsNone(auth.reason)
        # Closed application with a decision already.
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        app.refresh_from_db()
        auth = get_decision_authority(self.hod, app)
        self.assertFalse(auth.can_decide)
        self.assertEqual(auth.reason, "application_closed")

    def test_each_decision_writes_exactly_one_audit_event(self):
        app = self.submit()
        stage1 = self._stage(app, 1)
        decide(
            application_id=app.id,
            actor=self.hod,
            action="approve",
            comment="OK",
            expected_stage_version=stage1.version,
        )
        events = AuditEvent.objects.filter(action="leave_application.approve")
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.actor, self.hod)
        self.assertEqual(event.prev_state, "pending")
        self.assertEqual(event.new_state, "pending")
        self.assertEqual(event.metadata["stage_order"], 1)
        self.assertEqual(event.metadata["reason"], "OK")

    def test_final_approve_writes_approved_status_in_audit(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar)
        final = self._stage(app, 4)
        decide(
            application_id=app.id,
            actor=self.dvc,
            action="approve",
            comment="",
            expected_stage_version=final.version,
        )
        # Intermediate approvals also log leave_application.approve with
        # new_state "pending"; only the final DVC decision flips to "approved".
        event = AuditEvent.objects.get(
            action="leave_application.approve", new_state="approved"
        )
        self.assertEqual(event.prev_state, "pending")
        self.assertEqual(event.new_state, "approved")

    def test_no_balance_change_or_email_side_effect(self):
        app = self.submit()
        before = self.stub.get_leave_balance(app.employee_id, app.financial_year_label)
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        after = self.stub.get_leave_balance(app.employee_id, app.financial_year_label)
        self.assertEqual(before, after)
        self.assertIsNone(
            emit_approval_event(
                ApprovalEvent(
                    kind="application_finalised",
                    application_id=str(app.id),
                    stage_order=4,
                    action="approve",
                    cycle=1,
                    occurred_at=timezone.now(),
                )
            )
        )

    def test_workflow_snapshot_is_immutable_after_submission(self):
        app = self.submit()
        original = [
            (stage.stage_order, stage.role) for stage in app.stages.all()
        ]
        original_map = fixture_provider.FIXTURE_WORKFLOWS.copy()
        fixture_provider.FIXTURE_WORKFLOWS[("administration", "")] = ("registrar", "dvc")
        self.addCleanup(
            lambda: fixture_provider.FIXTURE_WORKFLOWS.update(original_map)
        )
        assign_workflow(app, actor=self.employee)
        app.refresh_from_db()
        self.assertEqual(
            [(stage.stage_order, stage.role) for stage in app.stages.all()],
            original,
        )


class VisibilityScopeTests(ApprovalFixtureMixin, TestCase):
    def setUp(self):
        self.setUpApprovals()
        # The locked academic fixture route is Supervisor -> HOD -> Registrar ->
        # DVC (no dean stage), but these tests assert Dean/Registrar/DVC
        # visibility. Override the map for this class only (the fixture provider
        # docstring sanctions per-department test overrides) and restore after.
        original_map = fixture_provider.FIXTURE_WORKFLOWS.copy()
        fixture_provider.FIXTURE_WORKFLOWS[("academic", "")] = (
            "supervisor",
            "hod",
            "dean",
            "registrar",
            "dvc",
        )
        self.addCleanup(
            lambda: fixture_provider.FIXTURE_WORKFLOWS.update(original_map)
        )

    def academic_submit(self):
        return self.submit(employee=self.academic)

    def test_view_access_only_for_reached_stages(self):
        app = self.academic_submit()
        self.assertEqual(app.current_stage.role, "supervisor")
        self.assertIsNotNone(get_view_access(self.supervisor, app))
        # Later, waiting-stage approvers cannot see it yet.
        self.assertIsNone(get_view_access(self.hod, app))
        self.assertIsNone(get_view_access(self.dvc, app))
        # Unrelated user never sees it.
        other = make_user(username="unrelated@test.luanar")
        self.assertIsNone(get_view_access(other, app))
        # An already-decided approver retains view access (read-only history).
        self.advance(app, self.supervisor)
        self.assertIsNotNone(get_view_access(self.supervisor, app))
        self.assertIsNotNone(get_view_access(self.hod, app))

    def test_supervisor_scope_is_full_history(self):
        app = self.academic_submit()
        view = get_view_access(self.supervisor, app)
        scope = get_leave_history_scope(view, self.academic)
        self.assertTrue(scope.available)
        self.assertEqual(scope.scope, "all")

    def test_hod_scope_is_full_only_within_department(self):
        self.set_profile(self.hod, department="Computer Science")

        app_in_department = self.academic_submit()
        self.advance(app_in_department, self.supervisor)
        view_hod = get_view_access(self.hod, app_in_department)
        scope = get_leave_history_scope(view_hod, self.academic)
        self.assertTrue(scope.available)
        self.assertEqual(scope.scope, "all")

        other = make_user(username="law@test.luanar", role="employee")
        self.set_profile(
            other, department="Law", category="academic", grade="F"
        )
        self.stub.register_employee(other, category="academic", grade="F")
        app_out = self.submit(employee=other)
        self.advance(app_out, self.supervisor)
        view = get_view_access(self.hod, app_out)
        self.assertFalse(get_leave_history_scope(view, other).available)

    def test_hod_fails_closed_without_own_profile(self):
        app = self.academic_submit()
        self.advance(app, self.supervisor)
        view = get_view_access(self.hod, app)
        self.assertFalse(get_leave_history_scope(view, self.academic).available)

    def test_dean_scope_is_full_only_within_faculty(self):
        # Faculty is the EmployeeProfile.department stand-in for now.
        self.set_profile(self.dean, department="Sciences")
        self.update_profile(self.academic, department="Sciences")
        app = self.academic_submit()
        self.advance(app, self.supervisor, self.hod)
        view = get_view_access(self.dean, app)
        scope = get_leave_history_scope(view, self.academic)
        self.assertTrue(scope.available)
        self.assertEqual(scope.scope, "all")

        self.update_profile(self.academic, department="Humanities")
        app_other = self.academic_submit()
        self.advance(app_other, self.supervisor, self.hod)
        view = get_view_access(self.dean, app_other)
        self.assertFalse(get_leave_history_scope(view, self.academic).available)

    def test_registrar_and_dvc_scope_is_current_financial_year(self):
        app = self.academic_submit()
        # Advance through the registrar too: the DVC stage is only non-waiting
        # (and thus viewable) once the registrar has decided.
        self.advance(app, self.supervisor, self.hod, self.dean, self.registrar)
        view = get_view_access(self.registrar, app)
        scope = get_leave_history_scope(view, self.academic)
        self.assertTrue(scope.available)
        self.assertEqual(scope.scope, "current_financial_year")
        view_dvc = get_view_access(self.dvc, app)
        scope = get_leave_history_scope(view_dvc, self.academic)
        self.assertTrue(scope.available)
        self.assertEqual(scope.scope, "current_financial_year")


class ApprovalApiTests(ApprovalFixtureMixin, TestCase):
    def setUp(self):
        self.setUpApprovals()
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_unauthenticated_requests_are_401(self):
        client = APIClient()
        self.assertEqual(
            client.get("/api/v1/approvals/capabilities/").status_code, 401
        )
        self.assertEqual(client.get("/api/v1/approvals/").status_code, 401)
        app = self.submit()
        self.assertEqual(
            client.get(f"/api/v1/approvals/{app.id}/").status_code, 401
        )
        self.assertEqual(
            client.post(f"/api/v1/approvals/{app.id}/decision/").status_code, 401
        )

    def test_employee_has_no_capabilities_and_empty_lists(self):
        self.authenticate(self.employee)
        body = self.client.get("/api/v1/approvals/capabilities/").data
        self.assertEqual(body, {"is_approver": False, "pending_count": 0})
        self.submit()
        response = self.client.get("/api/v1/approvals/", {"tab": "pending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_capabilities_pending_count(self):
        self.authenticate(self.hod)
        self.submit()
        body = self.client.get("/api/v1/approvals/capabilities/").data
        self.assertEqual(body["is_approver"], True)
        self.assertEqual(body["pending_count"], 1)

    def test_pending_tab_lists_only_my_stage_applications(self):
        app_a = self.submit(reason="A")
        app_b = self.submit(
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
            reason="B",
        )
        # A second HOD never sees apps that are with this HOD.
        other_hod = make_user(username="hod2@test.luanar", role="hod")

        self.authenticate(self.hod)
        response = self.client.get("/api/v1/approvals/", {"tab": "pending"})
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {str(app_a.id), str(app_b.id)})
        row = response.data["results"][0]
        self.assertEqual(row["reference"], app_a.reference_number)
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["my_decision"])
        self.assertEqual(row["department"], "")

        self.authenticate(other_hod)
        response = self.client.get("/api/v1/approvals/", {"tab": "pending"})
        self.assertEqual(response.data["results"], [])

    def test_pending_sort_is_oldest_submission_first(self):
        from datetime import timedelta

        older = self.submit(reason="old")
        LeaveApplication.objects.filter(pk=older.pk).update(
            submitted_at=timezone.now() - timedelta(days=1)
        )
        self.authenticate(self.hod)
        newer = self.submit(reason="newer")
        self.assertLess(older.submitted_at, newer.submitted_at)
        response = self.client.get("/api/v1/approvals/", {"tab": "pending"})
        rows = response.data["results"]
        self.assertEqual(rows[0]["reference"], older.reference_number)

    def test_search_by_reference_and_employee_name(self):
        self.submit(reason="A")
        self.authenticate(self.hod)
        response = self.client.get(
            "/api/v1/approvals/", {"tab": "pending", "q": "LV-2026-27-000001"}
        )
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(
            "/api/v1/approvals/", {"tab": "pending", "q": "employee@"}
        )
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(
            "/api/v1/approvals/", {"tab": "pending", "q": "zzz-no-match"}
        )
        self.assertEqual(response.data["results"], [])

    def test_pagination_page_size(self):
        for i in range(23):
            self.submit(reason=f"r{i}")
        self.authenticate(self.hod)
        response = self.client.get("/api/v1/approvals/", {"page_size": "5"})
        self.assertEqual(response.data["count"], 23)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNotNone(response.data["next"])

    def test_decided_tab_lists_applications_i_decided(self):
        app = self.submit()
        self.advance(app, self.hod)
        self.authenticate(self.hod)
        response = self.client.get("/api/v1/approvals/", {"tab": "decided"})
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], str(app.id))
        self.assertEqual(row["my_decision"]["action"], "approve")
        self.assertIsNotNone(row["my_decision"]["decided_at"])

        # The Dean has not decided anything yet.
        self.authenticate(self.dean)
        response = self.client.get("/api/v1/approvals/", {"tab": "decided"})
        self.assertEqual(response.data["results"], [])

    def test_detail_renders_full_review_payload(self):
        app = self.submit()
        # The employee and HOD need matching profiles so the history scope is
        # "all" for the HOD's review.
        self.set_profile(self.employee, department="Registry", category="administration")
        profile = self.set_profile(
            self.hod, department="Registry", category="administration"
        )
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/x/note.pdf",
            file_url="https://cdn.example.test/note.pdf",
            file_name="note.pdf",
            file_size=2048,
            content_type="application/pdf",
        )
        self.authenticate(self.hod)
        body = self.client.get(f"/api/v1/approvals/{app.id}/").data

        self.assertEqual(body["reference"], app.reference_number)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["submission_cycle"], 1)
        self.assertEqual(body["application"]["leave_type"], "Annual Leave")
        self.assertEqual(body["application"]["working_days"], 5)
        self.assertEqual(
            set(body["employee"].keys()),
            {
                "full_name",
                "staff_id",
                "designation",
                "department",
                "faculty",
                "grade",
                "date_of_appointment",
            },
        )
        self.assertEqual(body["employee"]["staff_id"], self.employee.username)
        self.assertEqual(body["balance"], {"entitlement": 24, "used": 0, "available": 24})
        self.assertTrue(body["leave_history"]["available"])
        self.assertEqual(body["documents"][0]["name"], "note.pdf")
        self.assertEqual(body["documents"][0]["size_bytes"], 2048)
        self.assertEqual(body["permissions"], {"can_decide": True, "reason": None})
        self.assertEqual(body["my_stage_role_label"], "Head of Department")
        self.assertEqual(len(body["stages"]), 4)
        current = body["current_stage"]
        self.assertEqual(current["order"], 1)
        self.assertEqual(current["next_role_label"], "Dean")
        self.assertFalse(current["is_final"])
        self.assertEqual(current["version"], 1)

    def test_detail_include_earlier_decision_comments(self):
        app = self.submit()
        self.advance(app, self.hod)
        self.authenticate(self.dean)
        body = self.client.get(f"/api/v1/approvals/{app.id}/").data
        stage1 = next(s for s in body["stages"] if s["order"] == 1)
        self.assertEqual(stage1["status"], "approved")
        self.assertEqual(stage1["action"], "approve")
        self.assertTrue(stage1["comment"])

    def test_waiting_stage_approver_gets_404(self):
        app = self.submit()
        self.authenticate(self.dvc)
        self.assertEqual(
            self.client.get(f"/api/v1/approvals/{app.id}/").status_code, 404
        )
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {"action": "approve", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_unrelated_user_gets_404(self):
        app = self.submit()
        other = make_user(username="unrelated@test.luanar")
        self.authenticate(other)
        self.assertEqual(
            self.client.get(f"/api/v1/approvals/{app.id}/").status_code, 404
        )

    def test_unknown_application_id_is_404(self):
        self.authenticate(self.hod)
        self.assertEqual(
            self.client.get(f"/api/v1/approvals/{uuid4()}/").status_code, 404
        )
        response = self.client.post(
            f"/api/v1/approvals/{uuid4()}/decision/",
            {"action": "approve", "comment": "", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_balance_unavailable_renders_nulls(self):
        app = self.submit()
        self.authenticate(self.hod)
        provider = mock.Mock()
        provider.get_leave_balance.side_effect = LeaveBalanceUnavailableError(
            "balance lookup failed"
        )
        with mock.patch(
            "workflows.approvals_serializers.get_provider", return_value=provider
        ):
            body = self.client.get(f"/api/v1/approvals/{app.id}/").data
        self.assertEqual(
            body["balance"], {"entitlement": None, "used": None, "available": None}
        )

    def test_detail_balance_unexpected_error_propagates(self):
        app = self.submit()
        self.authenticate(self.hod)
        provider = mock.Mock()
        provider.get_leave_balance.side_effect = RuntimeError("boom")
        with mock.patch(
            "workflows.approvals_serializers.get_provider", return_value=provider
        ):
            with self.assertRaises(RuntimeError):
                self.client.get(f"/api/v1/approvals/{app.id}/")

    def test_decision_endpoint_returns_updated_payload(self):
        app = self.submit()
        self.authenticate(self.hod)
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {
                "action": "approve",
                "comment": "",
                "stage_version": app.current_stage.version,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.data
        self.assertEqual(
            body["permissions"], {"can_decide": False, "reason": "already_decided"}
        )
        self.assertEqual(body["current_stage"]["order"], 2)
        self.assertEqual(body["status"], "pending")

    def test_decision_endpoint_400_on_missing_comment(self):
        app = self.submit()
        self.authenticate(self.hod)
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {
                "action": "reject",
                "comment": "   ",
                "stage_version": app.current_stage.version,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.data)

    def test_decision_endpoint_400_bad_action(self):
        app = self.submit()
        self.authenticate(self.hod)
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {
                "action": "cancel",
                "comment": "",
                "stage_version": app.current_stage.version,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("action", response.data)

    def test_decision_endpoint_409_on_stale_version(self):
        app = self.submit()
        self.authenticate(self.hod)
        stage1 = app.stages.get(stage_order=1)
        # The client opened the review at version 1 but the server has already
        # moved on (a conflicting, newer version); the decision must not land.
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {
                "action": "approve",
                "comment": "",
                "stage_version": stage1.version + 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 0)

    def test_decision_endpoint_403_already_decided(self):
        app = self.submit()
        self.advance(app, self.hod)
        self.authenticate(self.hod)
        stage = app.current_stage
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {"action": "approve", "comment": "", "stage_version": stage.version},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 1)

    def test_decision_endpoint_403_on_closed_application(self):
        app = self.submit()
        self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        self.authenticate(self.hod)
        stage = app.current_stage
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {"action": "reject", "comment": "late", "stage_version": stage.version},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @mock.patch("workflows.approvals_views.get_signed_download_url")
    def test_download_url_for_owned_document(self, mock_url):
        mock_url.return_value = "https://signed-url.test/note.pdf?token=abc"
        app = self.submit()
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/x/note.pdf",
            file_url="https://cdn.example.test/note.pdf",
            file_name="note.pdf",
            file_size=2048,
            content_type="application/pdf",
        )
        self.authenticate(self.hod)
        response = self.client.get(
            f"/api/v1/approvals/{app.id}/documents/{doc.id}/download-url/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://signed-url.test/note.pdf?token=abc")
        mock_url.assert_called_once_with("leave-documents/x/note.pdf", expires=60)

    def test_download_url_for_document_of_another_application_is_404(self):
        app = self.submit()
        other_app = self.submit(reason="other")
        doc = SupportingDocument.objects.create(
            application=other_app,
            file_path="leave-documents/x/other.pdf",
            file_url="https://cdn.example.test/other.pdf",
            file_name="other.pdf",
            file_size=1,
            content_type="application/pdf",
        )
        self.authenticate(self.hod)
        response = self.client.get(
            f"/api/v1/approvals/{app.id}/documents/{doc.id}/download-url/"
        )
        self.assertEqual(response.status_code, 404)

    @mock.patch("workflows.approvals_views.get_signed_download_url")
    def test_download_url_503_when_storage_unavailable(self, mock_url):
        mock_url.side_effect = ValueError("Supabase credentials are not configured.")
        app = self.submit()
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/x/note.pdf",
            file_url="https://cdn.example.test/note.pdf",
            file_name="note.pdf",
            file_size=2048,
            content_type="application/pdf",
        )
        self.authenticate(self.hod)
        response = self.client.get(
            f"/api/v1/approvals/{app.id}/documents/{doc.id}/download-url/"
        )
        self.assertEqual(response.status_code, 503)


class ApprovalApiAcademicTests(ApprovalFixtureMixin, TestCase):
    """Academic workflow: Supervisor is the first stage."""

    def setUp(self):
        self.setUpApprovals()
        self.client = APIClient()
        self.authenticate(self.supervisor)

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_supervisor_first_stage_pending(self):
        app = self.submit(employee=self.academic)
        body = self.client.get(f"/api/v1/approvals/{app.id}/").data
        self.assertEqual(body["my_stage_role_label"], "Supervisor")
        self.assertEqual(body["permissions"]["can_decide"], True)
        response = self.client.post(
            f"/api/v1/approvals/{app.id}/decision/",
            {
                "action": "approve",
                "comment": "",
                "stage_version": app.current_stage.version,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_stage"]["role_label"], "Head of Department")


class SeedApprovalsDevTests(TestCase):
    def test_seed_command_runs_idempotently(self):
        from django.core.management import call_command

        make_user(role="hr")
        make_approver_chain()
        call_command("seed_approvals_dev", verbosity=0)
        detail_count = lambda: LeaveApplication.objects.count()  # noqa: E731

        first = detail_count()
        self.assertGreater(first, 0)
        call_command("seed_approvals_dev", verbosity=0)
        self.assertEqual(detail_count(), first)
        self.assertGreater(ApplicationStage.objects.count(), 0)
        self.assertGreater(ApprovalDecision.objects.count(), 0)