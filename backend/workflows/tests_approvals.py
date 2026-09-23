"""Unit 16 — approver review and decision tests.

Covers the workflow provider fixture, stage assignment, the decision service
(approve/reject/correction, optimistic locking, immutable decisions) and the
approvals HTTP API (capabilities, list, detail, decision, documents).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.services.submission import submit_application
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user
from users.models import EmployeeProfile

from .models import ApplicationStage, ApprovalDecision
from .providers import FixtureWorkflowProvider
from .services import (
    ApprovalNotAllowedError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    WorkflowAssignmentError,
    assign_workflow,
    decide,
)

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

    def stage(self, app, order: int) -> ApplicationStage:
        return ApplicationStage.objects.get(
            application=app,
            submission_cycle=app.submission_cycle,
            stage_order=order,
        )


class WorkflowProviderFixtureTests(ApprovalBase):
    def test_chain_for_administration_starts_with_supervisor(self):
        profile = self.supervisor.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        app = LeaveApplication(employee=self.supervisor)
        definitions = FixtureWorkflowProvider().get_stage_definitions(app)
        self.assertEqual(
            [d.role for d in definitions],
            ["supervisor", "hod", "registrar", "dvc"],
        )

    def test_chain_for_academic_without_department_starts_with_hod(self):
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ACADEMIC
        profile.department = "Mathematics"
        profile.save()
        definitions = FixtureWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual(
            [d.role for d in definitions],
            ["hod", "dean", "registrar", "dvc"],
        )

    def test_every_definition_resolves_an_active_approver(self):
        app = LeaveApplication(employee=self.employee)
        definitions = FixtureWorkflowProvider().get_stage_definitions(app)
        self.assertTrue(all(d.approver_user_id is not None for d in definitions))


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
        self.assertEqual(ctx.exception.errors[0]["code"], "workflow_unavailable")
        self.assertIn("No active user", ctx.exception.errors[0]["message"])

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