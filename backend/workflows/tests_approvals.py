"""Unit 16 — approver review and decision tests.

Covers the workflow provider fixture, stage assignment, the decision service
(approve/reject/correction, optimistic locking, immutable decisions) and the
approvals HTTP API (capabilities, list, detail, decision, documents).
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
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
from .testing import (
    department_for,
    grant_approver_role,
    make_approver,
    make_section,
    make_team,
)
from .models import (
    ApplicationStage,
    ApprovalDecision,
    ApproverRole,
    Section,
    SectionMember,
    Team,
    Workflow,
)
from .providers import (
    DatabaseWorkflowProvider,
    WorkflowConfigError,
)
from .services import (
    ApprovalNotAllowedError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    WorkflowAssignmentError,
    assign_workflow,
    decide,
)
from .policies import (
    ViewAccess,
    get_decision_authority,
    get_leave_history_scope,
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
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "hod@luanar", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            "registrar@luanar",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        self.dvc = make_user(
            "dvc@luanar", role="dvc", first_name="Din", last_name="Vc"
        )
        self.dean = make_user(
            "dean@luanar", role="dean", first_name="Dena", last_name="Dean"
        )
        self.stub.register_employee(self.employee)
        EmployeeProfile.objects.create(
            user=self.employee,
            designation="Junior Officer",
            department=department_for("Administration"),
            grade="B",
        )
        EmployeeProfile.objects.create(
            user=self.supervisor,
            designation="Direct Supervisor",
            department=department_for("Administration"),
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

    def submit_as_approver(self, approver, role_code):
        """Submit a leave application owned by ``approver`` (their own request).

        A second person is put on the approver's own section first. The applicant
        is removed from every section's eligibility, so a section staffed only by
        the applicant resolves to nobody and the submission is refused outright —
        the test would never reach a decision guard at all. Adding a colleague is
        the configuration the product expects, and it lets the guard be exercised
        the way a user hits it.
        """
        self.stub.register_employee(approver)
        colleague = make_approver(
            role_code, username=f"cover-{role_code}@{approver.username}"
        )
        self.stub.workflow.register_approver(role_code, colleague)
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
            make_section(self.admin_workflow, index, role)
        self.academic_workflow = Workflow.objects.create(
            name="Academic chain",
            employee_category=EmployeeProfile.Category.ACADEMIC,
            effective_from=today,
            is_active=True,
        )
        for index, role in enumerate(("hod", "dean", "registrar", "dvc"), start=1):
            make_section(self.academic_workflow, index, role)

        # A team's workflow is what routes its members, so each workflow needs a
        # team behind it — and the employees need to be on one. ``registrar`` is
        # institution-wide, so it is a ``RoleAssignment`` rather than a member
        # row; that is the fallback branch the provider is meant to exercise.
        self.admin_team = make_team(
            "Admin team",
            ("supervisor", "hod"),
            workflow=self.admin_workflow,
            approvers={"supervisor": self.supervisor, "hod": self.hod},
        )
        self.academic_team = make_team(
            "Academic team",
            ("hod", "dean"),
            workflow=self.academic_workflow,
            approvers={"hod": self.hod, "dean": self.dean},
        )
        grant_approver_role(self.registrar, "registrar", institution_wide=True)
        grant_approver_role(self.dvc, "dvc", institution_wide=True)
        self._place_on_team(self.employee, self.admin_team)
        self._place_on_team(self.supervisor, self.admin_team)

    def _place_on_team(self, user, team):
        # The approvers created by ``make_user`` have a role but no profile: only
        # the two named in ``ApprovalBase.setUp`` get one. A team assignment needs
        # a profile, so create a plain one rather than making every test that
        # places an approver do it.
        try:
            profile = user.employee_profile
        except EmployeeProfile.DoesNotExist:
            profile = EmployeeProfile.objects.create(
                user=user,
                designation="Officer",
                department=department_for("Administration"),
                grade="B",
            )
        profile.team = team
        profile.save(update_fields=["team"])
        return profile

    def test_chain_for_administration_starts_with_supervisor(self):
        profile = self._place_on_team(self.supervisor, self.admin_team)
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        # The applicant is the supervisor themself, so the supervisor step is
        # appointed to somebody else. A step holds one approver, so the way to
        # let a supervisor submit their own leave is to name a different person
        # on that step \u2014 there is no second member to fall back to.
        supervisor_section = self.admin_workflow.sections.get(
            approver_role__code="supervisor"
        )
        deputy = make_user(
            "deputy-supervisor@luanar", role="supervisor", first_name="Dep"
        )
        EmployeeProfile.objects.create(
            user=deputy,
            designation="Deputy",
            department=department_for("Administration"),
            grade="E",
        )
        supervisor_section.approver = deputy
        supervisor_section.save(update_fields=["approver"])
        app = LeaveApplication(employee=self.supervisor)
        definitions = DatabaseWorkflowProvider().get_stage_definitions(app)
        self.assertEqual(
            [d.role for d in definitions],
            ["supervisor", "hod", "registrar", "dvc"],
        )
        self.assertEqual(definitions[0].approver_user_ids, (deputy.pk,))

    def test_a_step_the_applicant_holds_is_skipped_forwards(self):
        """An approver applicant does not approve their own leave (Unit 30).

        Their own stage is still planned \u2014 dropping it silently would make the
        history unreadable \u2014 but it is marked skipped, and the application opens
        at the next stage up instead of being refused.
        """
        profile = self._place_on_team(self.supervisor, self.admin_team)
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.supervisor)
        )
        self.assertEqual(
            [(d.role, d.skipped) for d in definitions],
            [
                ("supervisor", True),
                ("hod", False),
                ("registrar", False),
                ("dvc", False),
            ],
        )
        skipped = definitions[0]
        self.assertEqual(
            skipped.skip_reason, "Applicant cannot approve their own application."
        )
        # Nobody may act on a skipped stage, so it resolves to no one at all \u2014
        # which is exactly why it must not be a routable definition.
        self.assertEqual(skipped.approver_user_ids, ())

    def _place_on_admin_team(self, user):
        profile = self._place_on_team(user, self.admin_team)
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        return profile

    def test_the_applicants_final_stage_hands_the_application_to_hr(self):
        """The applicant is the DVC, the last step: there is no higher stage to
        open at, so an HR stage is appended rather than the application being
        refused or finalised by nobody (Unit 30)."""
        hr = make_user("hr-1@luanar", role=User.Role.HR, first_name="Ha")
        self._place_on_admin_team(self.dvc)

        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.dvc)
        )

        self.assertEqual(
            [(d.role, d.skipped) for d in definitions],
            [
                ("supervisor", True),
                ("hod", True),
                ("registrar", True),
                ("dvc", True),
                ("hr", False),
            ],
        )
        self.assertEqual(definitions[-1].approver_user_ids, (hr.pk,))
        self.assertEqual(definitions[-1].section_id, None)
        self.assertEqual(
            definitions[-1].history_scope, ApproverRole.HistoryScope.ALL
        )
        # The appended stage keeps the orders contiguous, so nothing downstream
        # that assumes 1..N has to know a stage was invented here.
        self.assertEqual([d.order for d in definitions], [1, 2, 3, 4, 5])

    def test_the_hr_destination_excludes_the_applicant(self):
        """HR is decided by somebody other than the person applying, so an HR
        account of their own does not put them in their own stage."""
        me = make_user("hr-applicant@luanar", role=User.Role.HR, first_name="Io")
        other = make_user("hr-other@luanar", role=User.Role.HR, first_name="Ot")
        self._place_on_admin_team(me)
        Section.objects.filter(
            workflow=self.admin_workflow, approver_role__code="dvc"
        ).update(approver=me)

        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=me)
        )

        self.assertEqual(definitions[-1].role, "hr")
        self.assertEqual(definitions[-1].approver_user_ids, (other.pk,))

    def test_no_other_hr_account_is_a_refusal_not_a_deadlock(self):
        """The sole HR account belongs to the applicant. Parking the
        application on a stage nobody may act would be worse than refusing it."""
        me = make_user("hr-only@luanar", role=User.Role.HR, first_name="Solo")
        self._place_on_admin_team(me)
        Section.objects.filter(
            workflow=self.admin_workflow, approver_role__code="dvc"
        ).update(approver=me)

        with self.assertRaises(WorkflowConfigError) as caught:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=me)
            )
        message = str(caught.exception)
        self.assertIn("Human Resources", message)
        self.assertIn("No other active", message)

    def test_no_hr_account_at_all_is_a_refusal(self):
        self._place_on_admin_team(self.dvc)
        User.objects.filter(role=User.Role.HR).update(is_active=False)

        with self.assertRaises(WorkflowConfigError) as caught:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.dvc)
            )
        self.assertIn("No other active", str(caught.exception))

    def test_an_inactive_hr_account_is_not_offered_the_application(self):
        active = make_user("hr-active@luanar", role=User.Role.HR, first_name="Ac")
        inactive = make_user("hr-gone@luanar", role=User.Role.HR, first_name="Go")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        self._place_on_admin_team(self.dvc)

        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.dvc)
        )

        self.assertEqual(definitions[-1].approver_user_ids, (active.pk,))

    def test_chain_for_academic_without_department_starts_with_hod(self):
        profile = self._place_on_team(self.employee, self.academic_team)
        profile.category = EmployeeProfile.Category.ACADEMIC
        profile.department = department_for("Mathematics")
        profile.save()
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual(
            [d.role for d in definitions],
            ["hod", "dean", "registrar", "dvc"],
        )

    def test_every_definition_resolves_an_active_approver(self):
        profile = self._place_on_team(self.employee, self.admin_team)
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        # Every step resolves to at least one person; a step with nobody is a
        # configuration error, so the provider would have raised above.
        self.assertTrue(all(d.approver_user_ids for d in definitions))

    def test_no_active_workflow_raises_config_error(self):
        # Deactivate rather than delete: teams PROTECT their workflow, and the
        # point of the test is that nothing is *applicable*.
        Workflow.objects.update(is_active=False)
        # A queryset update bypasses the ORM, so the already-fetched team would
        # still hand the provider a cached, active workflow. Drop the cache so
        # the provider sees what a fresh request would.
        self.admin_team.refresh_from_db()
        profile = self.employee.employee_profile
        profile.category = EmployeeProfile.Category.ADMINISTRATION
        profile.save()
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("inactive", str(ctx.exception))

    def test_retired_team_raises_config_error(self):
        """A team that has been retired stops routing, and says so.

        Retiring rather than deleting is why the team still exists: the
        application is pointed at it and the stages that prove who could decide
        it are its configuration.
        """
        self.admin_team.status = Team.Status.INACTIVE
        self.admin_team.save(update_fields=["status"])
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("inactive", str(ctx.exception))

    def test_draft_team_raises_config_error(self):
        """A team still being configured must not route anything.

        This is the case the boolean could not express: the team exists and its
        workflow is live, but HR has not finished staffing it, so routing to it
        would strand the employee at a step with nobody to act.
        """
        self.admin_team.status = Team.Status.DRAFT
        self.admin_team.save(update_fields=["status"])
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("still being set up", str(ctx.exception))

    def test_a_team_that_has_not_started_routing_raises_config_error(self):
        self.admin_team.effective_from = timezone.localdate() + timedelta(days=7)
        self.admin_team.save(update_fields=["effective_from"])
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("does not start until", str(ctx.exception))

    def test_a_team_whose_window_has_closed_raises_config_error(self):
        self.admin_team.effective_to = timezone.localdate() - timedelta(days=1)
        self.admin_team.save(update_fields=["effective_to"])
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("stopped routing applications on", str(ctx.exception))

    def test_a_team_inside_its_window_still_routes(self):
        """A bounded window is a way to retire a team on a date, not to break it."""
        self.admin_team.effective_from = timezone.localdate() - timedelta(days=30)
        self.admin_team.effective_to = timezone.localdate() + timedelta(days=30)
        self.admin_team.save(update_fields=["effective_from", "effective_to"])
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertTrue(definitions)

    def test_a_workflow_with_no_sections_raises_config_error(self):
        """A team always points at a workflow, but a workflow may be empty.

        ``Team.workflow`` is required, so "no workflow" is no longer a state a
        team can be in. The remaining way to have nothing to route is a workflow
        with no sections — an empty draft HR has not finished building.
        """
        self.admin_workflow.sections.all().delete()
        self.admin_team.refresh_from_db()
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("no active approval sections", str(ctx.exception))

    def test_future_dated_workflow_raises_config_error(self):
        """A scheduled-but-not-yet-effective workflow must not route anything."""
        from datetime import timedelta as _td

        from django.utils import timezone as _tz

        self.admin_workflow.effective_from = _tz.localdate() + _td(days=7)
        self.admin_workflow.save(update_fields=["effective_from"])
        self.admin_team.refresh_from_db()
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("does not start until", str(ctx.exception))

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
        # A section is claimed by whoever acts first, so nothing is assigned at
        # assignment time. The eligibility snapshot records who *may* act.
        self.assertIsNone(app.current_approver_id)
        self.assertIsNone(stages[0].assigned_approver_id)
        self.assertEqual(stages[0].eligible_approver_ids(), (self.supervisor.id,))

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
        app = self.submit_as_approver(self.supervisor, "supervisor")
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
        """The chain starts at section one whatever the applicant holds.

        Nothing is skipped, so the applicant sits on a live pending stage — and
        is refused there. The refusal is the snapshot, not the spine: they were
        removed from the stage's eligibility when the chain was materialised,
        and the guard would refuse them even if the spine named them.
        """
        app = self.submit_as_approver(self.hod, "hod")
        self.assertEqual(self.stage(app, 1).status, ApplicationStage.Status.PENDING)
        # The Supervisor's own section is untouched by the applicant holding
        # another role, so the chain opens with them.
        self.assertTrue(get_decision_authority(self.supervisor, app).can_decide)
        self.assertEqual(
            get_decision_authority(self.hod, app).reason, "self_application"
        )
        self.assertNotIn(
            self.hod.id, self.stage(app, 1).eligible_approver_ids()
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


class LeaveHistoryScopeTests(ApprovalBase):
    """The scope gate that decides whether an approver sees an applicant's
    leave history at all.

    ``get_leave_history_scope`` had no test of its own, which is how the
    ``same_department`` branch survived a schema change unexamined:
    ``EmployeeProfile.department`` became a foreign key in 8d472b3 (from a
    ``CharField``) while the comparison still stringified whatever it was
    handed, so a populated department raised ``AttributeError: 'Department'
    object has no attribute 'strip'`` and took the whole review payload to
    500. Four of the cases below are the four that used to crash.
    """

    def scope_for(self, history_scope, employee_profile, approver_profile):
        view = None
        if history_scope is not None:
            view = ViewAccess(2, "hod", "HOD", None, history_scope)
        return get_leave_history_scope(view, employee_profile, approver_profile)

    def profile(self, user):
        return EmployeeProfile.objects.get(user=user)

    def test_same_department_allows_the_applicants_own_department(self):
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_DEPARTMENT,
            self.profile(self.employee),
            self.profile(self.supervisor),
        )
        self.assertEqual(result, (True, "all"))

    def test_same_department_denies_another_department(self):
        approver = self.profile(self.supervisor)
        approver.department = department_for("Finance")
        approver.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_DEPARTMENT,
            self.profile(self.employee),
            approver,
        )
        self.assertEqual(result, (False, "all"))

    def test_same_department_denies_an_unrecorded_applicant_department(self):
        employee = self.profile(self.employee)
        employee.department = None
        employee.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_DEPARTMENT,
            employee,
            self.profile(self.supervisor),
        )
        self.assertEqual(result, (False, "all"))

    def test_same_department_denies_an_unrecorded_approver_department(self):
        approver = self.profile(self.supervisor)
        approver.department = None
        approver.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_DEPARTMENT,
            self.profile(self.employee),
            approver,
        )
        self.assertEqual(result, (False, "all"))

    def test_same_department_denies_an_approver_with_no_profile(self):
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_DEPARTMENT,
            self.profile(self.employee),
            None,
        )
        self.assertEqual(result, (False, "all"))

    def test_same_faculty_matches_on_equal_text(self):
        employee = self.profile(self.employee)
        approver = self.profile(self.supervisor)
        employee.faculty = "Science and Technology"
        approver.faculty = "  Science And Technology "
        employee.save()
        approver.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_FACULTY, employee, approver
        )
        self.assertEqual(result, (True, "all"))

    def test_same_faculty_denies_differing_text(self):
        employee = self.profile(self.employee)
        approver = self.profile(self.supervisor)
        employee.faculty = "Social Sciences"
        approver.faculty = "Engineering"
        employee.save()
        approver.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_FACULTY, employee, approver
        )
        self.assertEqual(result, (False, "all"))

    def test_blank_faculty_never_reads_as_a_match(self):
        """A field nobody filled in is not a field the two people share.

        The two fixtures both default to ``faculty=""``; matching them would
        widen an approver's history on the strength of an omission.
        """
        employee = self.profile(self.employee)
        approver = self.profile(self.supervisor)
        employee.faculty = ""
        approver.faculty = ""
        employee.save()
        approver.save()
        result = self.scope_for(
            ApproverRole.HistoryScope.SAME_FACULTY, employee, approver
        )
        self.assertEqual(result, (False, "all"))

    def test_all_scope_needs_no_profile_at_all(self):
        self.assertEqual(
            self.scope_for(
                ApproverRole.HistoryScope.ALL,
                self.profile(self.employee),
                None,
            ),
            (True, "all"),
        )

    def test_none_scope_reports_nothing(self):
        self.assertEqual(
            self.scope_for(
                ApproverRole.HistoryScope.NONE,
                self.profile(self.employee),
                self.profile(self.supervisor),
            ),
            (False, "none"),
        )

    def test_a_missing_view_reports_its_own_narrow_scope(self):
        self.assertEqual(
            self.scope_for(None, self.profile(self.employee), None),
            (False, "current_financial_year"),
        )

    def test_an_unrecognised_scope_falls_back_to_the_narrow_reading(self):
        """A value HR wrote by hand outside the choices must not widen anyone."""
        self.assertEqual(
            self.scope_for("everything", self.profile(self.employee), None),
            (True, "current_financial_year"),
        )


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
        app = self.submit_as_approver(self.supervisor, "supervisor")
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
        app = self.submit_as_approver(self.supervisor, "supervisor")
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

    def test_detail_survives_a_department_scoped_stage(self):
        """The 500 on the approval page, guarded.

        Stage 2 of this fixture is scoped to ``same_department``, and an
        approver who has a real department used to take ``GET
        /approvals/{id}/`` down with ``AttributeError: 'Department' object has
        no attribute 'strip'`` — the scope comparison stringified a foreign key
        that 8d472b3 made a reference row. The payload has to come back 200 and
        say the history is available, because both people sit in Administration.
        """
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        stage = app.stages.get(stage_order=2)
        self.assertEqual(stage.role, "hod")
        self.assertEqual(
            stage.history_scope, ApproverRole.HistoryScope.SAME_DEPARTMENT
        )
        EmployeeProfile.objects.create(
            user=self.hod,
            designation="Head of Department",
            department=department_for("Administration"),
            grade="E",
        )

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(self.url(f"{app.pk}/"))

        self.assertEqual(response.status_code, 200)
        history = response.data["history"]["leave_history"]
        self.assertTrue(history["available"])

    def test_detail_denies_department_history_across_departments(self):
        """The same stage, one row apart, must deny rather than 500.

        Availability is the whole job of ``same_department``: an approver outside
        the applicant's department sees no history, and the payload still reads
        as a normal 200 so the page can render the refusal.
        """
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        EmployeeProfile.objects.create(
            user=self.hod,
            designation="Head of Department",
            department=department_for("Finance"),
            grade="E",
        )

        self.client.force_authenticate(user=self.hod)
        response = self.client.get(self.url(f"{app.pk}/"))

        self.assertEqual(response.status_code, 200)
        history = response.data["history"]["leave_history"]
        self.assertFalse(history["available"])
        self.assertEqual(history["entries"], [])

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
