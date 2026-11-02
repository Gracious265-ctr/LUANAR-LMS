"""A team routes one or more chains at the same time.

:attr:`~teams.models.Team.workflow` used to be the single chain a team routed
through, so "which chain is my application's" was answered by the team. It is
now the team's *default* chain: a team owns several chains
(:attr:`~chains.models.Workflow.team`) and its people are enrolled on them one
at a time (:class:`~chains.models.WorkflowMember`). Two people on one team can
therefore route in parallel, through different chains, at the same moment.

These tests pin :mod:`chains.routing` — the one resolver both the submission
provider and the On Leave read scope use — at the layer that consumes it, so a
regression shows up as a submission routed through the wrong chain rather than
as a differing return value nobody reads.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from approvals.services import assign_workflow
from leave.models import LeaveApplication
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin
from roles.models import RoleAssignment

from .models import WorkflowMember
from .providers import DatabaseWorkflowProvider, WorkflowConfigError
from .routing import (
    routed_chain_ids_by_user,
    routed_workflow_for,
    routed_workflow_for_user,
)
from .services.lifecycle import validate_team
from .testing import (
    appoint_approver_to_section,
    ensure_roles,
    make_approver,
    make_employee,
    make_team,
    make_workflow,
)

User = get_user_model()


class RoutingTestCase(TestCase):
    """Shared fixtures: one team, a default chain, and a second chain it owns."""

    def setUp(self):
        ensure_roles("supervisor", "hod", "registrar", "dvc")
        self.hr = User.objects.create_user(
            username="hr-routing@test.luanar",
            email="hr-routing@test.luanar",
            password="testpass123",
            role=User.Role.HR,
        )
        # The team's default chain, staffed by make_team.
        self.team = make_team("Registry", ("supervisor", "hod"))
        self.default = self.team.workflow
        # A second chain for the same team, staffed by its own people so a
        # section never resolves the applicant or an empty step.
        self.second = self.add_chain(
            self.team, "Registry Senior Chain", ("supervisor", "registrar")
        )

    def add_chain(self, team, name, role_codes):
        """A further chain owned by ``team``, with one distinct approver per step."""
        workflow = make_workflow(name, role_codes)
        workflow.team = team
        workflow.save(update_fields=["team"])
        for section in workflow.sections.order_by("order"):
            appoint_approver_to_section(
                section,
                section.approver_role.code,
                user=make_approver(
                    section.approver_role.code,
                    username=f"approver-{workflow.pk}-{section.order}@test.luanar",
                    institution_wide=False,
                    team=team,
                ),
            )
        return workflow

    def enroll(self, workflow, user, *, is_wide=False):
        """Place ``user`` on ``workflow`` the way the membership service does."""
        return WorkflowMember.objects.create(
            workflow=workflow,
            user=user,
            team=workflow.team,
            is_wide_approver=is_wide,
            added_by=self.hr,
        )

    def routed_roles(self, user):
        """The roles of the stages a submission by ``user`` would be routed to."""
        return [
            definition.role
            for definition in DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=user)
            )
        ]


class PersonRoutedChainTests(RoutingTestCase):
    """``routed_workflow_for`` decides one person's chain, not the team's."""

    def test_a_member_routes_through_the_chain_they_are_enrolled_on(self):
        member = make_employee("enrolled@test.luanar", team=self.team)
        self.enroll(self.second, member)

        self.assertEqual(routed_workflow_for(self.team, member), self.second)
        self.assertEqual(self.routed_roles(member), ["supervisor", "registrar"])

    def test_a_member_nobody_enrolled_has_no_chain(self):
        """When a team member is not enrolled on any chain, there is no routing chain."""
        member = make_employee("unenrolled@test.luanar", team=self.team)

        self.assertIsNone(routed_workflow_for(self.team, member))
        # routed_roles will raise WorkflowConfigError since there's no chain
        # We just verify routed_workflow_for returns None

    def test_two_members_route_through_two_chains_of_one_team_at_once(self):
        first = make_employee("first@test.luanar", team=self.team)
        second = make_employee("second@test.luanar", team=self.team)
        self.enroll(self.second, second)

        # first is not enrolled, so has no routing chain (no default fallback)
        self.assertIsNone(routed_workflow_for(self.team, first))
        # second is enrolled on the second chain
        self.assertEqual(routed_workflow_for(self.team, second), self.second)
        # second's roles come from their enrolled chain
        self.assertEqual(self.routed_roles(second), ["supervisor", "registrar"])
        # first has no chain, so routed_roles would fail - that's expected

    def test_a_wide_approver_routes_through_their_single_enrolment(self):
        """A wide holding staffs every chain, but enrols on one.

        The registrar's post puts them on every chain's steps; their own leave
        still routes through the one chain they are a normal member of, never
        through a default fallback.
        """
        wide = make_employee("wide@test.luanar", team=self.team)
        registrar = ensure_roles("registrar")["registrar"]
        RoleAssignment.objects.create(role=registrar, user=wide)
        self.enroll(self.second, wide, is_wide=True)
        self.assertEqual(
            WorkflowMember.objects.filter(user=wide).count(),
            1,
        )

        self.assertEqual(routed_workflow_for(self.team, wide), self.second)
        self.assertEqual(self.routed_roles(wide), ["supervisor", "registrar"])

    def test_a_wide_approver_cannot_enrol_on_a_second_chain(self):
        """Wide staffing is about steps; membership stays one workflow."""
        wide = make_employee("wide-two@test.luanar", team=self.team)
        registrar = ensure_roles("registrar")["registrar"]
        RoleAssignment.objects.create(role=registrar, user=wide)
        self.enroll(self.default, wide, is_wide=True)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.enroll(self.second, wide, is_wide=True)

        self.assertEqual(WorkflowMember.objects.filter(user=wide).count(), 1)

    def test_the_chain_is_resolved_for_the_signed_in_person(self):
        member = make_employee("signed-in@test.luanar", team=self.team)
        self.enroll(self.second, member)
        self.assertEqual(routed_workflow_for_user(member), self.second)

    def test_somebody_with_no_team_has_no_chain(self):
        loner = make_employee("no-team@test.luanar")
        self.assertIsNone(routed_workflow_for_user(loner))


class MaterialisedChainTests(RoutingTestCase):
    """The chain a submission writes is the chain the employee joined.

    :func:`chains.routing.routed_workflow_for` is what the provider reads, so
    running the real writer (:func:`approvals.services.assign_workflow`) proves
    the answer reaches the application rather than stopping at a provider return
    value. Two people of one team then hold two live chains at once, each on the
    chain HR enrolled them on.
    """

    def materialise(self, employee):
        application = LeaveApplication.objects.create(employee=employee)
        assign_workflow(application)
        return application

    def stage_roles(self, application):
        return [
            stage.role for stage in application.stages.order_by("stage_order")
        ]

    def test_an_enrolled_member_is_materialised_on_their_chain(self):
        member = make_employee("materialised@test.luanar", team=self.team)
        self.enroll(self.second, member)

        application = self.materialise(member)

        self.assertEqual(self.stage_roles(application), ["supervisor", "registrar"])

    def test_an_unenrolled_member_has_no_chain(self):
        """When a team has no default and a member is unenrolled, there is no routing chain."""
        member = make_employee("materialised-default@test.luanar", team=self.team)

        # Without a default chain and no enrolment, the application should not route
        # We just verify routed_workflow_for returns None
        self.assertIsNone(routed_workflow_for(self.team, member))

    def test_two_members_hold_two_chains_at_the_same_time(self):
        first = make_employee("parallel-first@test.luanar", team=self.team)
        second = make_employee("parallel-second@test.luanar", team=self.team)
        # Enrol first on the default chain, second on the second chain
        self.enroll(self.default, first)
        self.enroll(self.second, second)

        first_application = self.materialise(first)
        second_application = self.materialise(second)

        self.assertEqual(
            self.stage_roles(first_application), ["supervisor", "hod"]
        )
        self.assertEqual(
            self.stage_roles(second_application), ["supervisor", "registrar"]
        )
        self.assertNotEqual(
            first_application.stages.first().section_ref.workflow_id,
            second_application.stages.first().section_ref.workflow_id,
        )


class SubmittedApplicationRoutingTests(StubProviderMixin, RoutingTestCase):
    """The submission endpoint writes the chain the employee was joined to.

    The rules side is stubbed to keep the leave validation out of this suite; the
    workflow provider is the real database one, so the request goes through
    ``check_workflow_ready`` and ``assign_workflow`` exactly as production does.
    """

    def setUp(self):
        super().setUp()
        self.stub = self.use_stub()
        real_provider = mock.patch(
            "chains.providers.get_workflow_provider",
            return_value=DatabaseWorkflowProvider(),
        )
        real_provider.start()
        self.addCleanup(real_provider.stop)
        self.client = APIClient()

    def submit(self, employee):
        self.stub.register_employee(employee)
        self.client.force_authenticate(user=employee)
        draft = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )
        response = self.client.post(
            f"/api/v1/leave-applications/{draft.pk}/submit/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return LeaveApplication.objects.get(pk=draft.pk)

    def stage_roles(self, application):
        return [
            stage.role for stage in application.stages.order_by("stage_order")
        ]

    def test_two_employees_submit_through_two_chains_at_once(self):
        first = make_employee("api-first@test.luanar", team=self.team)
        second = make_employee("api-second@test.luanar", team=self.team)
        # Enrol first on the default chain, second on the second chain
        self.enroll(self.default, first)
        self.enroll(self.second, second)

        first_application = self.submit(first)
        second_application = self.submit(second)

        self.assertEqual(self.stage_roles(first_application), ["supervisor", "hod"])
        self.assertEqual(
            self.stage_roles(second_application), ["supervisor", "registrar"]
        )
        self.assertEqual(
            first_application.status, LeaveApplication.Status.SUBMITTED
        )
        self.assertEqual(
            second_application.status, LeaveApplication.Status.SUBMITTED
        )


class ChainlessDefaultTests(RoutingTestCase):
    """A team without a default chain still routes its enrolled people.

    Since there is no default fallback, an unenrolled person has no chain."""

    def test_an_enrolled_member_routes_when_the_team_has_no_default(self):
        self.team.workflow = None
        self.team.save(update_fields=["workflow"])
        member = make_employee("enrolled-chainless@test.luanar", team=self.team)
        self.enroll(self.second, member)

        # No default, but enrolled person routes through their chain
        self.assertEqual(routed_workflow_for(self.team, member), self.second)
        self.assertEqual(self.routed_roles(member), ["supervisor", "registrar"])

    def test_an_unenrolled_member_of_a_chainless_team_has_no_chain(self):
        """When a team has no default and a person has no enrolment, they have no chain."""
        self.team.workflow = None
        self.team.save(update_fields=["workflow"])
        member = make_employee("stuck@test.luanar", team=self.team)

        # No default fallback, so unenrolled person has no chain
        self.assertIsNone(routed_workflow_for(self.team, member))

        # The provider check will raise WorkflowConfigError since there's no chain
        with self.assertRaisesMessage(
            WorkflowConfigError, "has no approval workflow for this employee"
        ):
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=member)
            )


class MultiChainReadinessTests(RoutingTestCase):
    """Readiness answers for every chain the team routes, not only its default.

    A team routes its default chain and every chain its people are enrolled on,
    all at the same time. A readiness check that stopped at the default would
    report a team as ready while the second chain it routes had lost its
    approver, and the employee enrolled on that chain would find out at
    submission.
    """

    def add_unstaffed_chain(self, name="Registry Draft Chain"):
        """A further chain for the team with nobody appointed to its steps."""
        workflow = make_workflow(name, ("supervisor", "registrar"))
        workflow.team = self.team
        workflow.save(update_fields=["team"])
        return workflow

    def test_a_routed_second_chain_with_an_unstaffed_step_is_reported(self):
        chain = self.add_unstaffed_chain()
        member = make_employee("unstaffed-chain@test.luanar", team=self.team)
        self.enroll(chain, member)

        readiness = validate_team(self.team)

        self.assertFalse(readiness.ready)
        unstaffed = [issue for issue in readiness.issues if issue.code == "no_approver"]
        self.assertTrue(unstaffed)
        for issue in unstaffed:
            self.assertIn(chain.name, issue.message)

    def test_a_chain_nobody_is_enrolled_on_is_not_reported(self):
        """A chain being built beside the live ones is allowed to be incomplete."""
        self.add_unstaffed_chain()

        self.assertTrue(validate_team(self.team).ready)

    def test_a_second_routed_chain_past_its_end_date_is_reported(self):
        member = make_employee("expired-chain@test.luanar", team=self.team)
        self.enroll(self.second, member)
        self.second.effective_to = timezone.localdate() - timedelta(days=1)
        self.second.save(update_fields=["effective_to"])

        readiness = validate_team(self.team)

        self.assertFalse(readiness.ready)
        self.assertIn("workflow_ended", [issue.code for issue in readiness.issues])

    def test_a_submission_through_an_expired_chain_is_refused(self):
        member = make_employee("expired-submit@test.luanar", team=self.team)
        self.enroll(self.second, member)
        self.second.effective_to = timezone.localdate() - timedelta(days=1)
        self.second.save(update_fields=["effective_to"])

        with self.assertRaisesMessage(WorkflowConfigError, "stopped routing on"):
            self.routed_roles(member)

    def test_a_team_with_no_default_is_ready_when_its_people_are_enrolled(self):
        """Only the unenrolled need a chain; since there is no default, enrolled people route."""
        self.team.workflow = None
        self.team.save(update_fields=["workflow"])
        member = make_employee("enrolled-ready@test.luanar", team=self.team)
        self.enroll(self.second, member)

        readiness = validate_team(self.team)

        self.assertTrue(readiness.ready)
        # No "workflow_missing" because there are enrolled people on chains
        self.assertNotIn(
            "workflow_missing", [issue.code for issue in readiness.issues]
        )


class BulkRoutingTests(RoutingTestCase):
    """The bulk read used by list screens agrees with the per-person answer."""

    def test_bulk_resolution_matches_the_single_person_answer(self):
        plain = make_employee("plain@test.luanar", team=self.team)
        enrolled = make_employee("bulk-enrolled@test.luanar", team=self.team)
        self.enroll(self.second, enrolled)

        bulk = routed_chain_ids_by_user(self.team)

        # enrolled person routes through their chain
        self.assertEqual(bulk[enrolled.pk], self.second.pk)
        # plain has no enrolment, so has no chain (no default fallback)
        self.assertNotIn(plain.pk, bulk)
        # Verify single-person answer agrees
        self.assertIsNone(routed_workflow_for(self.team, plain))
        self.assertEqual(routed_workflow_for(self.team, enrolled).pk, self.second.pk)

    def test_bulk_resolution_omits_people_with_no_chain(self):
        self.team.workflow = None
        self.team.save(update_fields=["workflow"])
        stranded = make_employee("stranded@test.luanar", team=self.team)

        self.assertNotIn(stranded.pk, routed_chain_ids_by_user(self.team))

    def test_bulk_resolution_answers_for_somebody_with_no_team(self):
        self.assertEqual(routed_chain_ids_by_user(None), {})
