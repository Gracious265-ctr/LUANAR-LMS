"""Unit 16 — approver review and decision tests.

Covers the workflow provider fixture, stage assignment, the decision service
(approve/reject/correction, optimistic locking, immutable decisions) and the
approvals HTTP API (capabilities, list, detail, decision, documents).
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from audit.models import AuditEntry
from leave.cancellations.models import LeaveBalanceTransaction
from leave.models import FinancialYear, LeaveApplication
from leave.services.exceptions import ApplicationFinalisationError
from leave.services.submission import submit_application
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user
from users.models import EmployeeProfile

from .events import (
    APPLICATION_FINALISED,
    DECISION_RECORDED,
    _consumers,
    _reset_consumers_for_tests,
    register_consumer,
)
from .models import (
    ApplicationStage,
    ApprovalDecision,
    Workflow,
    WorkflowStage,
)
from .providers import (
    DatabaseWorkflowProvider,
    WorkflowConfigError,
    resolve_applicable_workflow,
)
from .services import (
    ApprovalNotAllowedError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    WorkflowAssignmentError,
    assign_workflow,
    decide,
)
from .policies import get_decision_authority

User = get_user_model()

ANNUAL = {"leave_type_id": 1, "start_date": EARLIEST_ANNUAL_START, "reason": "Family visit"}


class ApprovalBase(StubProviderMixin, APITestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.employee = make_user(
            "employee@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        self.supervisor = make_user(
            "supervisor@luanar",
            role=User.Role.SUPERVISOR,
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "hod@luanar", role=User.Role.HOD, first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "registrar@luanar",
            role=User.Role.REGISTRAR,
            first_name="Rej",
            last_name="Registrar",
        )
        self.dvc = make_user(
            "dvc@luanar", role=User.Role.DVC, first_name="Din", last_name="Vc"
        )
        self.dean = make_user(
            "dean@luanar", role=User.Role.DEAN, first_name="Dena", last_name="Dean"
        )
        self.stub.register_employee(self.employee)
        EmployeeProfile.objects.create(
            user=self.employee,
            designation="Junior Officer",
            department="Administration",
            grade="B",
        )
        EmployeeProfile.objects.create(
            user=self.supervisor,
            designation="Direct Supervisor",
            department="Administration",
            grade="E",
        )
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
            ("dvc", self.dvc),
        ):
            self.stub.workflow.register_approver(role, user)

    def make_submitted(self, end_offset=3):
        start = EARLIEST_ANNUAL_START
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=start + timedelta(days=end_offset),
            **ANNUAL,
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def submit_as_approver(self, approver):
        """Submit a leave application owned by ``approver`` (their own request)."""
        self.stub.register_employee(approver)
        start = EARLIEST_ANNUAL_START
        app = LeaveApplication.objects.create(
            employee=approver,
            start_date=start,
            end_date=start + timedelta(days=3),
            leave_type_id=1,
            reason="Own leave",
        )
        return submit_application(user=approver, application_id=app.pk)

    def stage(self, app, order: int) -> ApplicationStage:
        return ApplicationStage.objects.get(
            application=app,
            submission_cycle=app.submission_cycle,
            stage_order=order,
        )


class WorkflowProviderDatabaseTests(ApprovalBase):
    """Unit 21 — the real ``DatabaseWorkflowProvider`` (D5)."""

    def setUp(self):
        super().setUp()
        from django.utils import timezone

        today = timezone.localdate()
        self.admin_workflow = Workflow.objects.create(
            name="Admin chain",
            employee_category=EmployeeProfile.Category.ADMINISTRATION,
            effective_from=today,
            is_active=True,
        )
        for index, role in enumerate(
            ("supervisor", "hod", "registrar", "dvc"), start=1
        ):
            WorkflowStage.objects.create(
                workflow=self.admin_workflow, order=index, approver_role=role
            )
        self.academic_workflow = Workflow.objects.create(
            name="Academic chain",
            employee_category=EmployeeProfile.Category.ACADEMIC,
            effective_from=today,
            is_active=True,
        )
        for index, role in enumerate(("hod", "dean", "registrar", "dvc"), start=1):
            WorkflowStage.objects.create(
                workflow=self.academic_workflow, order=index, approver_role=role
            )

    def test_chain_for_administration_starts_with_supervisor(self):
        profile = self.supervisor.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        app = LeaveApplication(employee=self.supervisor)
        definitions = DatabaseWorkflowProvider().get_stage_definitions(app)
        self.assertEqual(
            [d.role for d in definitions],
            ["supervisor", "hod", "registrar", "dvc"],
        )

    def test_chain_for_academic_without_department_starts_with_hod(self):
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ACADEMIC
        profile.department = "Mathematics"
        profile.save()
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual(
            [d.role for d in definitions],
            ["hod", "dean", "registrar", "dvc"],
        )

    def test_every_definition_resolves_an_active_approver(self):
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertTrue(all(d.approver_user_id is not None for d in definitions))

    def test_no_active_workflow_raises_config_error(self):
        Workflow.objects.all().delete()
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        with self.assertRaises(WorkflowConfigError):
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )

    def test_exact_scope_wins_over_category_any(self):
        from django.utils import timezone

        exact = Workflow.objects.create(
            name="Maths chain",
            employee_category=EmployeeProfile.Category.ACADEMIC,
            department="Mathematics",
            effective_from=timezone.localdate(),
            is_active=True,
        )
        WorkflowStage.objects.create(
            workflow=exact, order=1, approver_role="supervisor"
        )
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ACADEMIC
        profile.department = "Mathematics"
        profile.save()
        resolved = resolve_applicable_workflow(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual(resolved.pk, exact.pk)

    def test_inactive_workflow_is_not_applicable(self):
        Workflow.objects.all().update(is_active=False)
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        self.assertIsNone(
            resolve_applicable_workflow(LeaveApplication(employee=self.employee))
        )


class AssignmentTests(ApprovalBase):
    def test_assign_creates_chain_with_single_pending_stage(self):
        app = self.make_submitted()
        stages = list(
            ApplicationStage.objects.filter(
                application=app, submission_cycle=app.submission_cycle
            ).order_by("stage_order")
        )
        self.assertEqual(len(stages), 4)
        self.assertEqual(
            [stage.status for stage in stages],
            [
                ApplicationStage.Status.PENDING,
                ApplicationStage.Status.WAITING,
                ApplicationStage.Status.WAITING,
                ApplicationStage.Status.WAITING,
            ],
        )
        self.assertFalse(stages[0].is_final)
        self.assertTrue(stages[-1].is_final)
        self.assertEqual(app.current_stage_id, stages[0].pk)
        self.assertEqual(app.current_approver_id, self.supervisor.id)
        self.assertEqual(stages[0].assigned_approver_id, self.supervisor.id)

    def test_assign_requires_an_active_approver_for_every_stage(self):
        self.stub.workflow.strict = True
        self.stub.workflow.approvers.clear()
        draft = LeaveApplication.objects.create(employee=self.employee, **ANNUAL)
        with self.assertRaises(WorkflowAssignmentError):
            assign_workflow(draft)

    def test_submission_without_workflow_is_a_validation_failure(self):
        self.stub.workflow.strict = True
        self.stub.workflow.approvers.clear()
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )
        from leave.services.submission import ValidationFailedError

        with self.assertRaises(ValidationFailedError) as ctx:
            submit_application(user=self.employee, application_id=app.pk)
        self.assertEqual(ctx.exception.errors[0].code, "workflow_unavailable")
        self.assertIn("No active approver", ctx.exception.errors[0].message)

    def test_assign_is_idempotent(self):
        app = self.make_submitted()
        first = app.current_stage
        again = assign_workflow(app)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(ApplicationStage.objects.filter(application=app).count(), 4)


class DecisionServiceTests(ApprovalBase):
    def test_approve_advances_one_stage(self):
        app = self.make_submitted()
        result = decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        app.refresh_from_db()
        self.assertEqual(result.status, LeaveApplication.Status.SUBMITTED)
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(self.stage(app, 1).status, ApplicationStage.Status.APPROVED)
        self.assertEqual(self.stage(app, 1).decision_version, 2)
        self.assertEqual(self.stage(app, 2).status, ApplicationStage.Status.PENDING)
        self.assertEqual(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.APPROVED,
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=str(app.pk),
                reason="",
            ).count(),
            1,
        )

    def test_full_approval_chain_finalises(self):
        app = self.make_submitted()
        for user in (self.supervisor, self.hod, self.registrar, self.dvc):
            app = decide(
                application_id=app.pk,
                actor=user,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
            app.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 4)
        self.assertEqual(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.APPROVED, target_id=str(app.pk)
            ).count(),
            4,
        )

    def test_reject_stops_the_chain_with_comment(self):
        app = self.make_submitted()
        result = decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.REJECT,
            comment="Insufficient documentation.",
            expected_version=1,
        )
        result.refresh_from_db()
        self.assertEqual(result.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(
            self.stage(app, 1).status, ApplicationStage.Status.REJECTED
        )
        self.assertEqual(
            self.stage(app, 2).status, ApplicationStage.Status.WAITING
        )
        self.assertEqual(
            AuditEntry.objects.get(
                action=AuditEntry.Action.REJECTED, target_id=str(app.pk)
            ).reason,
            "Insufficient documentation.",
        )

    def test_reject_requires_a_comment(self):
        app = self.make_submitted()
        with self.assertRaises(ApprovalValidationError) as ctx:
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.REJECT,
                expected_version=1,
            )
        self.assertIn("comment", ctx.exception.errors)

    def test_return_for_correction_sets_correction_required(self):
        app = self.make_submitted()
        result = decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.RETURN_FOR_CORRECTION,
            comment="Please review the leave dates.",
            expected_version=1,
        )
        result.refresh_from_db()
        self.assertEqual(
            result.status, LeaveApplication.Status.CORRECTION_REQUIRED
        )
        self.assertEqual(self.stage(app, 1).status, ApplicationStage.Status.CORRECTION_REQUESTED)
        self.assertEqual(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.CORRECTION_REQUESTED,
                target_id=str(app.pk),
            ).count(),
            1,
        )

    def test_double_submit_records_exactly_one_decision(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        with self.assertRaises(ApprovalStageChangedError):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=2,
            )
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 1)

    def test_stale_version_is_a_conflict(self):
        app = self.make_submitted()
        with self.assertRaises(ApprovalStageChangedError):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=0,
            )

    def test_not_current_stage_is_forbidden(self):
        app = self.make_submitted()
        with self.assertRaises(ApprovalNotAllowedError) as ctx:
            decide(
                application_id=app.pk,
                actor=self.hod,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
        self.assertEqual(ctx.exception.reason, "not_current_stage")

    def test_self_approval_is_forbidden(self):
        app = self.submit_as_approver(self.supervisor)
        with self.assertRaises(ApprovalNotAllowedError) as ctx:
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
        self.assertEqual(ctx.exception.reason, "self_application")
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 0)

    def test_self_approval_is_forbidden_at_any_stage(self):
        """An approver's own application starts after their stage, and they are
        refused if a live stage still points at them (invariant 12.3)."""
        app = self.submit_as_approver(self.hod)
        self.assertEqual(
            self.stage(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            get_decision_authority(self.supervisor, app).reason, "not_current_stage"
        )
        self.assertEqual(
            get_decision_authority(self.hod, app).reason, "self_application"
        )
        with self.assertRaises(ApprovalNotAllowedError) as ctx:
            decide(
                application_id=app.pk,
                actor=self.hod,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
        self.assertEqual(ctx.exception.reason, "self_application")
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 0)

    def test_approver_from_earlier_stage_cannot_act_again(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        with self.assertRaises(ApprovalStageChangedError):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=2,
            )
        with self.assertRaises(ApprovalStageChangedError):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 1)

    def test_decision_is_append_only(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        decision = ApprovalDecision.objects.get(application=app)
        with self.assertRaises(Exception):
            decision.delete()
        with self.assertRaises(Exception):
            ApprovalDecision.objects.filter(pk=decision.pk).update(action="reject")
        with self.assertRaises(Exception):
            decision.comment = "edited"
            decision.save()


class ApprovalAPITests(ApprovalBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.supervisor)

    def url(self, suffix=""):
        return f"/api/v1/approvals/{suffix}"

    def make_second_submitted(self, employee=None):
        owner = employee or self.employee
        start = EARLIEST_ANNUAL_START + timedelta(days=10)
        app = LeaveApplication.objects.create(
            employee=owner,
            start_date=start,
            end_date=start + timedelta(days=3),
            leave_type_id=1,
            reason="Second leave",
        )
        return submit_application(user=owner, application_id=app.pk)

    def test_capabilities_for_approver(self):
        response = self.client.get(self.url("capabilities/"))
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertTrue(body["is_approver"])
        self.assertIsInstance(body["pending_count"], int)

    def test_capabilities_for_employee(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.url("capabilities/"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_approver"])

    def test_pending_list_lists_only_my_pending(self):
        app = self.make_submitted()
        other = self.make_second_submitted()
        response = self.client.get(self.url("?tab=pending"))
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        ids = [row["id"] for row in results]
        # supervisor holds stage 1 of both apps (stub chain),
        # so both pending apps appear while awaiting supervisor.
        self.assertIn(str(app.pk), ids)
        self.assertIn(str(other.pk), ids)
        self.assertTrue(all(row["status"] == "pending" for row in results))

    def test_decided_list_includes_my_decisions(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        decide(
            application_id=app.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        other = self.make_second_submitted()
        decide(
            application_id=other.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        decide(
            application_id=other.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.REJECT,
            comment="Duplicate application.",
            expected_version=1,
        )
        self.client.force_authenticate(user=self.hod)
        response = self.client.get(self.url("?tab=decided"))
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(str(app.pk), ids)
        self.assertIn(str(other.pk), ids)
        decided = next(row for row in response.data["results"] if row["id"] == str(other.pk))
        self.assertEqual(decided["status"], "rejected")
        self.assertEqual(decided["my_decision"]["action"], "reject")

    def test_pending_list_supports_search(self):
        app = self.make_submitted()
        other = self.make_second_submitted()
        response = self.client.get(
            self.url(f"?tab=pending&q={app.reference_number}")
        )
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [str(app.pk)])
        self.assertNotIn(str(other.pk), ids)

    def test_employee_cannot_use_approver_endpoints(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.url(""))
        self.assertEqual(response.status_code, 403)

    def test_self_application_decision_returns_403(self):
        app = self.submit_as_approver(self.supervisor)
        response = self.client.post(
            self.url(f"{app.pk}/decision/"),
            {"action": "approve", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["reason"], "self_application")
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 0)

    def test_self_application_review_is_not_reachable(self):
        """The applicant's own stage is bypassed, so it grants no review access."""
        app = self.submit_as_approver(self.supervisor)
        response = self.client.get(self.url(f"{app.pk}/"))
        self.assertEqual(response.status_code, 404)

    def test_leave_history_excludes_drafts(self):
        app = self.make_submitted()
        LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.DRAFT,
            **ANNUAL,
        )
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url(f"{app.pk}/"))
        self.assertEqual(response.status_code, 200)
        entries = response.data["history"]["leave_history"]["entries"]
        statuses = {entry["status"] for entry in entries}
        self.assertNotIn("draft", statuses)

    def test_detail_returns_whitelisted_review_payload(self):
        app = self.make_submitted()
        self.client.force_authenticate(user=self.supervisor)
        response = self.client.get(self.url(f"{app.pk}/"))
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertIn("application", body)
        self.assertIn("employee_info", body)
        self.assertIn("rules", body)
        self.assertIn("balance", body)
        self.assertIn("documents", body)
        self.assertIn("history", body)
        self.assertIn("workflow", body)
        self.assertIn("my_decision", body)
        self.assertEqual(body["application"]["reference"], app.reference_number)
        self.assertEqual(body["workflow"]["state"], "pending")
        stages = body["workflow"]["stages"]
        self.assertEqual([s["order"] for s in stages], [1, 2, 3, 4])
        self.assertTrue(
            all("assigned_approver" in s and "status" in s for s in stages)
        )

    def test_detail_review_payload_with_active_financial_year(self):
        FinancialYear.objects.create(
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )
        app = self.make_submitted()
        other = self.make_second_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        decide(
            application_id=app.pk,
            actor=self.hod,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        self.client.force_authenticate(user=self.registrar)

        response = self.client.get(self.url(f"{app.pk}/"))
        self.assertEqual(response.status_code, 200)
        history = response.data["history"]["leave_history"]
        self.assertTrue(history["available"])
        self.assertEqual(history["scope"], "current_financial_year")
        refs = [entry["reference"] for entry in history["entries"]]
        self.assertIn(other.reference_number, refs)
        self.assertNotIn(app.reference_number, refs)

    def test_detail_audit_history_survives_a_system_actor_entry(self):
        """A system-actor audit entry must not 500 the whole review payload.

        The document render task records its outcome with ``actor=None`` (a
        system action, per Unit 23b). The review payload used to dereference
        ``entry.actor`` unconditionally, so one failed render made
        ``GET /approvals/{id}/`` return 500 for every approver of the
        application.
        """
        app = self.make_submitted()
        AuditEntry.objects.create(
            actor=None,
            action=AuditEntry.Action.DOCUMENT_FAILED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=str(app.pk),
            target_summary=app.reference_number or "",
            detail={"status": "failed"},
        )

        response = self.client.get(self.url(f"{app.pk}/"))
        self.assertEqual(response.status_code, 200)
        history = response.data["history"]["audit_history"]
        system_entries = [
            entry for entry in history if entry["action"] == "document_failed"
        ]
        self.assertEqual(len(system_entries), 1)
        self.assertEqual(system_entries[0]["actor"], "System")
        # A human entry in the same payload still reads as the person.
        self.assertTrue(
            any(entry["actor"] for entry in history if entry["action"] == "submitted")
        )

    def test_detail_404_for_unrelated_user(self):
        app = self.make_submitted()
        employee2 = make_user("employee2@luanar", role=User.Role.EMPLOYEE)
        self.stub.register_employee(employee2)
        other = self.make_second_submitted(employee=employee2)
        self.client.force_authenticate(user=self.hod)
        gated = [self.url(f"{app.pk}/"), self.url(f"{other.pk}/")]
        for url in gated:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_employee_info_never_leaks(self):
        app = self.make_submitted()
        response = self.client.get(self.url(f"{app.pk}/"))
        body = response.data
        self.assertEqual(body["employee_info"]["name"], "Ken Employee")
        self.assertEqual(body["balance"]["available"], "24")
        self.assertIsInstance(body["balance"]["entitlement"], str)

    def test_approve_via_api(self):
        app = self.make_submitted()
        current = app.current_stage
        response = self.client.post(
            self.url(f"{app.pk}/decision/"),
            {
                "action": "approve",
                "stage_version": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["current_stage"]["order"], current.stage_order + 1)

    def test_reject_via_api_requires_comment(self):
        app = self.make_submitted()
        response = self.client.post(
            self.url(f"{app.pk}/decision/"),
            {
                "action": "reject",
                "stage_version": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("errors", response.data)

    def test_decision_by_outsider_is_403(self):
        app = self.make_submitted()
        self.client.force_authenticate(user=self.dvc)
        response = self.client.post(
            self.url(f"{app.pk}/decision/"),
            {
                "action": "approve",
                "stage_version": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data["reason"], "not_current_stage")

    def test_duplicate_decision_via_api_is_409(self):
        app = self.make_submitted()
        self.client.post(
            self.url(f"{app.pk}/decision/"),
            {"action": "approve", "stage_version": 1},
            format="json",
        )
        response = self.client.post(
            self.url(f"{app.pk}/decision/"),
            {"action": "approve", "stage_version": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 1)

    def test_document_download_url(self):
        from leave.models import SupportingDocument

        app = self.make_submitted()
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/x/sample.pdf",
            file_url="https://storage.example/sample.pdf?signed",
            file_name="sample.pdf",
            file_size=1024,
            content_type="application/pdf",
        )
        response = self.client.get(
            self.url(f"{app.pk}/documents/{doc.pk}/download-url/")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(doc.pk))
        self.assertEqual(response.data["name"], "sample.pdf")
        self.assertTrue(response.data["download_url"])

    def test_document_download_url_fallback_without_supabase(self):
        from unittest import mock

        from leave.models import SupportingDocument

        app = self.make_submitted()
        doc = SupportingDocument.objects.create(
            application=app,
            file_path="leave-documents/x/sample.pdf",
            file_url="https://storage.example/cached.pdf",
            file_name="sample.pdf",
            file_size=1024,
            content_type="application/pdf",
        )
        with mock.patch(
            "leave.services.storage.signed_document_url",
            side_effect=ValueError("no supabase"),
        ):
            response = self.client.get(
                self.url(f"{app.pk}/documents/{doc.pk}/download-url/")
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["download_url"], "https://storage.example/cached.pdf")


def _restore_consumers(previous):
    """Put the global approval-event bus back as it was found."""
    _reset_consumers_for_tests()
    _consumers.extend(previous)


class FinalisationWiringTests(ApprovalBase):
    """Unit 25 — the final approval deducts balance and announces itself (D4, D5).

    Before this unit ``decide()`` only flipped the status to ``APPROVED``. It
    never touched the annual-balance ledger, the event-kind condition was
    inverted (a rejection announced ``application_finalised``), and nothing
    caught either because the assertion on approval covered status alone.
    """

    def capture_events(self):
        """Register an event-capturing consumer, restoring the real bus after."""
        events = []
        previous = list(_consumers)
        _reset_consumers_for_tests()
        register_consumer(events.append)
        self.addCleanup(_restore_consumers, previous)
        return events

    def decide_all(self, app, action, *, last_only_patch=None):
        approvers = (self.supervisor, self.hod, self.registrar, self.dvc)
        for index, user in enumerate(approvers):
            is_last = index == len(approvers) - 1
            if is_last and last_only_patch is not None:
                with last_only_patch():
                    result = decide(
                        application_id=app.pk,
                        actor=user,
                        action=action,
                        expected_version=1,
                    )
            else:
                result = decide(
                    application_id=app.pk,
                    actor=user,
                    action=action,
                    expected_version=1,
                )
            app.refresh_from_db()
        return app

    def deductions(self, app):
        return LeaveBalanceTransaction.objects.filter(
            application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
        )

    # --- D5: event kinds ------------------------------------------------

    def test_intermediate_approval_emits_decision_recorded(self):
        app = self.make_submitted()
        events = self.capture_events()
        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )
        self.assertEqual([e.kind for e in events], [DECISION_RECORDED])

    def test_final_approval_emits_application_finalised(self):
        app = self.make_submitted()
        events = self.capture_events()
        for user in (self.supervisor, self.hod, self.registrar, self.dvc):
            with self.captureOnCommitCallbacks(execute=True):
                decide(
                    application_id=app.pk,
                    actor=user,
                    action=ApprovalDecision.Action.APPROVE,
                    expected_version=1,
                )
            app.refresh_from_db()
        self.assertEqual(
            [e.kind for e in events],
            [DECISION_RECORDED] * 3 + [APPLICATION_FINALISED],
        )

    def test_rejection_emits_decision_recorded_not_finalised(self):
        """The inverted condition used to file a rejection as finalized."""
        app = self.make_submitted()
        events = self.capture_events()
        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.REJECT,
                comment="Insufficient documentation.",
                expected_version=1,
            )
        self.assertEqual([e.kind for e in events], [DECISION_RECORDED])
        self.assertNotIn(APPLICATION_FINALISED, [e.kind for e in events])

    def test_correction_required_emits_decision_recorded_not_finalised(self):
        app = self.make_submitted()
        events = self.capture_events()
        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.RETURN_FOR_CORRECTION,
                comment="Please attach the medical note.",
                expected_version=1,
            )
        self.assertEqual([e.kind for e in events], [DECISION_RECORDED])

    # --- D4: the deduction ----------------------------------------------

    def test_full_approval_records_exactly_one_deduction(self):
        app = self.make_submitted()
        self.decide_all(app, ApprovalDecision.Action.APPROVE)
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        deduction = self.deductions(app)
        self.assertEqual(deduction.count(), 1)
        entry = deduction.get()
        self.assertEqual(entry.employee_id, self.employee.id)
        self.assertEqual(entry.leave_type, app.leave_type_id)
        self.assertEqual(entry.days, app.working_days)
        self.assertEqual(entry.financial_year, app.financial_year_label)
        self.assertTrue(entry.carry_forward_eligible)

    def test_rejection_records_no_deduction(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.REJECT,
            comment="Insufficient documentation.",
            expected_version=1,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(self.deductions(app).count(), 0)

    def test_intermediate_approvals_record_no_deduction_yet(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertEqual(self.deductions(app).count(), 0)

    def test_non_deducting_leave_type_records_no_deduction(self):
        """Compassionate leave does not draw on the annual balance."""
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=4,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=4),  # 5 working days
            reason="Bereavement",
        )
        app = submit_application(user=self.employee, application_id=app.pk)
        self.decide_all(app, ApprovalDecision.Action.APPROVE)
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.deductions(app).count(), 0)

    def test_deduction_failure_rolls_the_approval_back(self):
        """D4: the deduction is business state, so a failure undoes the approval."""
        app = self.make_submitted()
        with mock.patch(
            "leave.services.finalise.record_deduction",
            side_effect=ApplicationFinalisationError("ledger unavailable"),
        ):
            with self.assertRaises(ApplicationFinalisationError):
                self.decide_all(app, ApprovalDecision.Action.APPROVE)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertEqual(LeaveBalanceTransaction.objects.count(), 0)
        self.assertEqual(
            ApprovalDecision.objects.filter(
                application=app, action=ApprovalDecision.Action.APPROVE
            ).count(),
            3,
            "the three committed stages survive; only the failing one rolls back",
        )
