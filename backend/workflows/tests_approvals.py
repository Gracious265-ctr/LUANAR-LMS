<<<<<<< HEAD
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
=======
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
    team_for,
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
            team=team_for("Administration"),
            grade="B",
        )
        EmployeeProfile.objects.create(
            user=self.supervisor,
            designation="Direct Supervisor",
            team=team_for("Administration"),
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
            effective_from=today,
            is_active=True,
        )
        for index, role in enumerate(
            ("supervisor", "hod", "registrar", "dvc"), start=1
        ):
            make_section(self.admin_workflow, index, role)
        self.academic_workflow = Workflow.objects.create(
            name="Academic chain",
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
                team=team_for("Administration"),
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
            team=team_for("Administration"),
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

    def test_chain_for_academic_on_the_academic_team_starts_with_hod(self):
        """Routing follows the applicant's team, whatever the person's category.

        The team carries no academic/administration split of its own: the chain
        that governs an applicant is the one belonging to the team they are on.
        """
        profile = self._place_on_team(self.employee, self.academic_team)
        profile.category = EmployeeProfile.Category.ACADEMIC
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
>>>>>>> feature/plans-teams
        with self.assertRaises(Exception):
            decision.delete()
        with self.assertRaises(Exception):
            ApprovalDecision.objects.filter(pk=decision.pk).update(action="reject")
<<<<<<< HEAD

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

    @mock.patch("workflows.approvals_views.get_storage_backend")
    def test_download_url_for_owned_document(self, mock_backend):
        backend = mock.Mock()
        backend.signed_url.return_value = "https://signed-url.test/note.pdf?token=abc"
        mock_backend.return_value = backend
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
        backend.signed_url.assert_called_once_with("leave-documents/x/note.pdf", expires=60)

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

    @mock.patch("workflows.approvals_views.get_storage_backend")
    def test_download_url_503_when_storage_unavailable(self, mock_backend):
        backend = mock.Mock()
        backend.signed_url.side_effect = ValueError(
            "Supabase credentials are not configured."
        )
        mock_backend.return_value = backend
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
=======
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
>>>>>>> feature/plans-teams
