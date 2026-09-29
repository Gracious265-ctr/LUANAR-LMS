"""Configuring a team end to end: create it, validate it, put it in force.

A team is the object HR actually works with, and these tests exercise it the way
the product now asks HR to work: name it, describe the chain it needs, check the
configuration, and only then let it route anything.

The three properties worth stating up front, because the rest of the file is
mostly about them:

**A team that is being built does not route.** ``DRAFT`` is the state a team
spends most of its life in, and it is invisible to the routing engine. The old
boolean could not express it, so a half-staffed team looked live and only failed
at submission — from the employee's side, at the worst moment.

**Every problem is reported, and the team is left alone.** Validation returns the
whole list rather than the first failure, and a refused activation keeps the team
in draft with the configuration HR wrote intact, so a refusal is a to-do list and
not a dead end.

**What an application was submitted against does not change.** These tests also
cover the membership history and the stage snapshots that make that true: a
membership that ends is closed, not deleted, and an application already inside a
chain keeps the approvers it was materialised with.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.services.submission import ValidationFailedError, submit_application
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin
from users.models import EmployeeProfile

from .models import (
    ApplicationStage,
    ApprovalDecision,
    ApproverRole,
    Section,
    SectionMember,
    Team,
    Workflow,
)
from .providers import DatabaseWorkflowProvider, WorkflowConfigError
from .services import (
    TeamActionError,
    activate_team,
    add_section_member,
    create_team,
    deactivate_team,
    decide,
    is_approver_user,
    remove_section_member,
    validate_team,
)
from .testing import DEV_PASSWORD, ensure_roles, make_approver, make_workflow

User = get_user_model()

#: The stub rules provider's reference "today" is 2026-09-21, so the earliest
#: annual start is the first date satisfying the notice period.
ANNUAL_START = EARLIEST_ANNUAL_START

TEAMS_URL = "/api/v1/teams/"
MEMBERS_URL = "/api/v1/section-members/"


class TeamConfigurationBase(TestCase):
    """An HR client, a team being built, and the roles its chain needs."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@teamflow.test",
            email="hr@teamflow.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.employee = User.objects.create_user(
            username="emp@teamflow.test",
            email="emp@teamflow.test",
            password=DEV_PASSWORD,
            first_name="Ebo",
            role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(self.hr)
        # Not institution-wide: these people are on the team's steps, which is
        # the case under test. A global holder would quietly stand in for an
        # unstaffed step and make a broken configuration look whole.
        self.supervisor = make_approver(
            "supervisor", username="sup@teamflow.test", institution_wide=False
        )
        self.hod = make_approver(
            "hod", username="hod@teamflow.test", institution_wide=False
        )
        self.chain = [
            {"name": "Supervisor approval", "approver_role": "supervisor", "members": [self.supervisor.pk]},
            {"name": "Head of Department approval", "approver_role": "hod", "members": [self.hod.pk]},
        ]

    def create_team(self, name="Administration team", **extra) -> dict:
        payload: dict = {
            "name": name,
            "description": "Administration approval chain",
            "new_workflow": {"sections": self.chain},
        }
        payload.update(extra)
        response = self.client.post(TEAMS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def activate(self, team_id: int) -> dict:
        response = self.client.post(f"{TEAMS_URL}{team_id}/activate/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def read(self, team_id: int) -> dict:
        response = self.client.get(f"{TEAMS_URL}{team_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def place_employee(self, team: Team):
        EmployeeProfile.objects.update_or_create(
            user=self.employee,
            defaults={"department": "Administration", "team": team},
        )
        # Writing the profile caches it on the user instance, holding on to the
        # Team object the caller passed — which may be a read taken before the
        # team was activated. Dropping the cache means the routing assertions
        # below are reading what is in the database, not what the test remembers.
        self.employee.refresh_from_db()

    def use_real_workflow_provider(self):
        """Undo the stub's workflow provider, leaving the rules provider stubbed.

        The two are stubbed together because most routing tests want a fixed
        chain. These want a real one: the question is what the *team's*
        configuration resolves to, which a stub would answer by fiat.
        """
        patcher = mock.patch(
            "workflows.providers.get_workflow_provider",
            return_value=DatabaseWorkflowProvider(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)


class TeamCreationTests(TeamConfigurationBase):
    """A team and its whole chain, written in one pass."""

    def test_a_team_is_created_with_its_workflow_sections_and_members(self):
        team = self.create_team()
        self.assertEqual(team["status"], Team.Status.DRAFT)
        self.assertTrue(team["workflow_name"])

        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["supervisor", "hod"],
        )
        self.assertEqual(
            set(
                stored.workflow.sections.get(approver_role__code="supervisor")
                .members.values_list("user_id", flat=True)
            ),
            {self.supervisor.pk},
        )

    def test_the_chain_is_ordered_by_the_order_given(self):
        """Steps run top to bottom, not in the order the payload happened to have.

        A chain whose order depended on submission order would let a client
        silently reshuffle a live approval sequence by re-sending the same steps.
        """
        team = self.create_team(
            name="Reversed team",
            new_workflow={"sections": list(reversed(self.chain))},
        )
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["hod", "supervisor"],
        )

    def test_a_named_chain_is_used_verbatim(self):
        team = self.create_team(
            new_workflow={"name": "ICT leave chain", "sections": self.chain}
        )
        self.assertEqual(Team.objects.get(pk=team["id"]).workflow.name, "ICT leave chain")

    def test_a_clashing_chain_name_is_suffixed_rather_than_rejected(self):
        """The team name is what HR typed; a chain name collision is our problem.

        Rejecting a team because somebody else already called their chain
        "Administration workflow" would make a name they did not choose into a
        hard failure.
        """
        Workflow.objects.create(name="Administration workflow")
        team = self.create_team()
        self.assertNotEqual(
            Team.objects.get(pk=team["id"]).workflow.name, "Administration workflow"
        )

    def test_a_team_owns_its_chain(self):
        """Two teams never end up on the same chain, even by name collision.

        The one-to-one is the rule that makes "edit this team's steps" safe: if a
        chain could be shared, saving one team's form would re-route every other
        team pointing at it.
        """
        first = self.create_team(name="First team")
        second = self.create_team(name="Second team")
        self.assertNotEqual(first["workflow"], second["workflow"])
        self.assertEqual(
            Workflow.objects.filter(team__isnull=False).count(),
            Team.objects.count(),
        )

    def test_a_team_must_describe_its_chain(self):
        response = self.client.post(
            TEAMS_URL, {"name": "Nothing team"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_workflow", response.data)
        self.assertFalse(Team.objects.filter(name="Nothing team").exists())

    def test_a_workflow_sent_on_create_is_ignored(self):
        """``workflow`` is read-only, so an old client cannot attach a chain.

        The field stays in the response, which means a client with it cached can
        still send it. Honouring it would put a new team on somebody else's
        chain, which is the exact outcome the team-owned chain rules out.
        """
        other = self.create_team(name="Other team")
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Copying team",
                "workflow": other["workflow"],
                "new_workflow": {"sections": self.chain},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotEqual(
            Team.objects.get(pk=response.data["id"]).workflow_id, other["workflow"]
        )

    def test_a_chain_with_no_steps_is_refused(self):
        response = self.client.post(
            TEAMS_URL,
            {"name": "Empty team", "new_workflow": {"sections": []}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_workflow", response.data)

    def test_an_unknown_or_deactivated_role_is_refused_before_anything_is_written(self):
        """A bad role fails the request, and leaves no half-built team behind.

        Everything lands in one transaction precisely so this is true: an empty
        workflow with no team is a row nobody will ever find or clean up.
        """
        self.assertEqual(Team.objects.count(), 0)
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Bad role team",
                "new_workflow": {
                    "sections": [
                        {"name": "Step", "approver_role": "not-a-role", "members": []}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Team.objects.count(), 0)
        self.assertEqual(Workflow.objects.count(), 0)

    def test_a_deactivated_role_cannot_be_used_in_a_new_chain(self):
        role = ensure_roles("dean")["dean"]
        role.is_active = False
        role.save(update_fields=["is_active"])
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Retired role team",
                "new_workflow": {
                    "sections": [
                        {"name": "Dean step", "approver_role": "dean", "members": []}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Team.objects.count(), 0)

    def test_a_deactivated_person_cannot_be_staffed_from_the_team_form(self):
        self.supervisor.is_active = False
        self.supervisor.save(update_fields=["is_active"])
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Bad member team",
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Supervisor step",
                            "approver_role": "supervisor",
                            "members": [self.supervisor.pk],
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Team.objects.count(), 0)

    def test_a_person_cannot_be_listed_twice_on_the_same_step(self):
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Duplicate team",
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Supervisor step",
                            "approver_role": "supervisor",
                            "members": [self.supervisor.pk, self.supervisor.pk],
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Team.objects.count(), 0)

    def test_one_person_may_sit_on_two_steps_of_the_same_chain(self):
        """Sections exist for exactly this: a person holding two points."""
        team = self.create_team(
            name="Two step team",
            new_workflow={
                "sections": [
                    {"name": "First look", "approver_role": "supervisor", "members": [self.supervisor.pk]},
                    {"name": "Second look", "approver_role": "hod", "members": [self.supervisor.pk]},
                ]
            },
        )
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(SectionMember.objects.filter(user=self.supervisor).count(), 2)

    def test_creation_is_audited_for_both_the_team_and_its_chain(self):
        team = self.create_team()
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM,
                action=AuditEntry.Action.CREATED,
                target_id=str(team["id"]),
            ).exists()
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.CREATED,
        )
        self.assertEqual(entry.detail["after"]["created_with_team"], "Administration team")
        self.assertEqual(
            [
                s["approver_role"]
                for s in entry.detail["after"]["workflow"]["sections"]
            ],
            ["supervisor", "hod"],
        )

    def test_non_hr_cannot_configure_a_team(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Sneaky team",
                "new_workflow": {
                    "sections": [
                        {"name": "Step", "approver_role": "supervisor", "members": [self.supervisor.pk]}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Team.objects.count(), 0)


class TeamChainEditingTests(TeamConfigurationBase):
    """Editing a team's chain, which happens on the team and nowhere else.

    A chain is written in the same request as the team, so its steps are edited
    in the same request as the team. The team form is the only writer, which
    means these tests are the only place the "edit the steps" path is covered —
    and they are what stops a later change from quietly re-introducing a second
    place to edit a chain.
    """

    def test_the_steps_can_be_rewritten_by_saving_the_team(self):
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {"name": "Supervisor", "approver_role": "supervisor"},
                        {"name": "Dean", "approver_role": "dean"},
                    ]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["supervisor", "dean"],
        )

    def test_editing_the_steps_leaves_the_team_itself_alone(self):
        """The chain is rewritten in place, not swapped for a new one.

        Swapping the chain would strand every application inside it, because
        their stages point at the sections the team used to have.
        """
        team = self.create_team()
        original_chain = team["workflow"]
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "name": "Renamed team",
                "new_workflow": {
                    "sections": [{"name": "Only step", "approver_role": "supervisor"}]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(stored.workflow_id, original_chain)
        self.assertEqual(stored.name, "Renamed team")

    def test_reordering_keeps_each_step_and_its_people(self):
        """A reorder is the same steps in a new order, not a new set of steps.

        Sections are identified by their role and name, so moving one keeps its
        roster. Rebuilding them empty would make a drag in the form silently
        strip the approvers, which is the one way a reorder could hurt someone.
        """
        team = self.create_team()
        sections = list(
            Team.objects.get(pk=team["id"]).workflow.sections.order_by("order")
        )
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {"name": s.name, "approver_role": s.approver_role.code}
                        for s in reversed(sections)
                    ]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["hod", "supervisor"],
        )
        self.assertEqual(
            set(
                stored.workflow.sections.get(approver_role__code="hod").members.values_list(
                    "user_id", flat=True
                )
            ),
            {self.hod.pk},
        )

    def test_renaming_a_step_rebuilds_it_empty(self):
        """A step with a different role or name is a different step.

        Carrying the old roster across would hand a new role a set of approvers
        nobody asked for. The step comes back visibly empty instead, and the
        readiness check is what says so.
        """
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {"name": "Renamed supervisor step", "approver_role": "supervisor"},
                        {
                            "name": "Head of Department approval",
                            "approver_role": "hod",
                        },
                    ]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        chain = Team.objects.get(pk=team["id"]).workflow
        renamed = chain.sections.get(name="Renamed supervisor step")
        self.assertEqual(renamed.members.count(), 0)
        # The step that did not change kept its roster, so renaming one step is
        # a local change rather than a reason to restaff the whole chain.
        self.assertEqual(
            chain.sections.get(name="Head of Department approval").members.count(), 1
        )

    def test_editing_the_steps_is_audited_against_the_chain(self):
        team = self.create_team()
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [{"name": "Single step", "approver_role": "supervisor"}]
                }
            },
            format="json",
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.UPDATED,
            target_id=str(team["workflow"]),
        )
        self.assertEqual(entry.detail["team"], "Administration team")

    def test_the_chain_can_be_renamed_with_the_team(self):
        team = self.create_team()
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"new_workflow": {"name": "ICT leave chain", "sections": self.chain}},
            format="json",
        )
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.name, "ICT leave chain"
        )

    def test_renaming_a_team_does_not_alter_its_chain_name(self):
        """Renaming a team leaves the chain alone unless the chain is renamed too.

        Otherwise a PATCH that only changes a team's display name would give it a
        new chain name every time, and the audit trail would fill up with
        changes nobody made.
        """
        team = self.create_team()
        chain_name = team["workflow_name"]
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/", {"name": "Better name"}, format="json"
        )
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.name, chain_name
        )

    def test_editing_the_steps_does_not_change_the_status(self):
        """Chain edits are configuration, not lifecycle.

        A team is put in force by activating it, so a form save that happens to
        include a steps change must not quietly do that too.
        """
        team = self.create_team()
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [{"name": "Step", "approver_role": "supervisor"}]
                },
                "status": Team.Status.ACTIVE,
            },
            format="json",
        )
        self.assertEqual(Team.objects.get(pk=team["id"]).status, Team.Status.DRAFT)

    def test_an_empty_step_list_is_refused_on_edit(self):
        """A team whose steps were all deleted would route nothing."""
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"new_workflow": {"sections": []}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.sections.count(), 2
        )

    def test_a_bad_role_is_refused_on_edit_and_leaves_the_steps_alone(self):
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [{"name": "Step", "approver_role": "not-a-role"}]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.sections.count(), 2
        )

    def test_adding_people_to_a_step_happens_on_the_team_page_not_the_form(self):
        """The form edits steps; a roster is one person at a time.

        Adding or removing one approver is an audited action of its own with its
        own effective dates, so it is not folded into "save the whole chain".
        """
        team = self.create_team()
        second = make_approver("supervisor", username="sup2@config.test")
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Supervisor",
                            "approver_role": "supervisor",
                            "members": [self.supervisor.pk, second.pk],
                        },
                        {"name": "Hod", "approver_role": "hod"},
                    ]
                }
            },
            format="json",
        )
        section = Team.objects.get(pk=team["id"]).workflow.sections.get(
            approver_role__code="supervisor"
        )
        self.assertEqual(
            set(section.members.values_list("user_id", flat=True)),
            {self.supervisor.pk, second.pk},
        )


class TeamValidationTests(TeamConfigurationBase):
    """Checking a team before it is allowed to affect anyone."""

    def test_a_fully_staffed_team_is_ready(self):
        team = Team.objects.get(pk=self.create_team()["id"])
        readiness = validate_team(team)
        self.assertTrue(readiness.ready, readiness.issues)
        self.assertEqual(readiness.issues, ())

    def test_validation_reports_nothing_wrong_with_a_good_team(self):
        team = self.create_team()
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ready"])
        self.assertEqual(response.data["issues"], [])

    def test_a_step_nobody_can_act_for_is_named(self):
        team = self.create_team(
            name="Gap team",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": [self.supervisor.pk]},
                    {"name": "Head of Department step", "approver_role": "hod", "members": []},
                ]
            },
        )
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        issue = response.data["issues"][0]
        self.assertEqual(issue["code"], "no_approver")
        self.assertEqual(issue["section"], 2)
        self.assertIn("Head of Department", issue["message"])

    def test_every_problem_is_reported_at_once(self):
        """A configuration with three broken steps should take one pass to fix.

        Reporting only the first would make a long, tedious loop of fixing one
        step, re-submitting, and discovering the next.
        """
        team = self.create_team(
            name="Three gaps",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []},
                    {"name": "Head step", "approver_role": "hod", "members": []},
                    {"name": "Dean step", "approver_role": "dean", "members": []},
                ]
            },
        )
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertEqual(
            sorted(issue["section"] for issue in response.data["issues"]), [1, 2, 3]
        )

    def test_a_step_whose_only_approver_is_deactivated_is_reported(self):
        """A membership whose account is switched off resolves to nobody.

        The roster still shows the name, so this is the failure HR cannot see by
        looking at the screen: the step looks staffed and nobody can sign it.
        """
        team = self.create_team()
        self.hod.is_active = False
        self.hod.save(update_fields=["is_active"])
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertEqual(
            [i["code"] for i in response.data["issues"]], ["no_approver"]
        )

    def test_a_step_on_a_deactivated_role_is_reported(self):
        team = self.create_team()
        ApproverRole.objects.filter(code="hod").update(is_active=False)
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertEqual(
            [i["code"] for i in response.data["issues"]], ["inactive_role"]
        )

    def test_a_chain_with_no_active_steps_is_reported(self):
        team = Team.objects.get(pk=self.create_team()["id"])
        team.workflow.sections.update(is_active=False)
        response = self.client.post(
            f"{TEAMS_URL}{team.pk}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertIn("no_sections", [i["code"] for i in response.data["issues"]])

    def test_a_retired_workflow_is_reported(self):
        team = Team.objects.get(pk=self.create_team()["id"])
        team.workflow.is_active = False
        team.workflow.save(update_fields=["is_active"])
        response = self.client.post(
            f"{TEAMS_URL}{team.pk}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertIn(
            "workflow_inactive", [i["code"] for i in response.data["issues"]]
        )

    def test_an_inverted_effective_window_is_reported(self):
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "effective_from": "2026-06-01",
                "effective_to": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("effective_to", response.data)

    def test_a_window_that_has_already_closed_blocks_activation(self):
        team = self.create_team(
            effective_from="2020-01-01", effective_to="2020-12-31"
        )
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertIn("window_ended", [i["code"] for i in response.data["issues"]])

    def test_two_active_teams_in_one_department_are_flagged(self):
        """Not an engine conflict — a human one, and usually an accident.

        Each employee still follows their own team, so nothing is ambiguous to
        the routing engine. It is ambiguous to whoever reads the configuration
        next, so activation makes HR say out loud that sharing is intended.
        """
        self.create_team(name="Registry team", department="Registrar")
        second = self.create_team(name="Records team", department="Registrar")
        self.activate(self.create_team_status_lookup("Registry team"))
        response = self.client.post(
            f"{TEAMS_URL}{second['id']}/validate/", format="json"
        )
        self.assertFalse(response.data["ready"])
        self.assertIn(
            "department_conflict", [i["code"] for i in response.data["issues"]]
        )

    def test_a_team_with_no_department_never_conflicts(self):
        first = self.create_team(name="No dept one")
        second = self.create_team(name="No dept two")
        self.activate(first["id"])
        response = self.client.post(
            f"{TEAMS_URL}{second['id']}/validate/", format="json"
        )
        self.assertTrue(response.data["ready"], response.data["issues"])

    def create_team_status_lookup(self, name: str) -> int:
        return Team.objects.get(name=name).pk

    def test_validation_changes_nothing(self):
        team = self.create_team()
        before = self.read(team["id"])
        self.client.post(f"{TEAMS_URL}{team['id']}/validate/", format="json")
        self.assertEqual(self.read(team["id"])["status"], before["status"])
        self.assertFalse(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM, target_id=str(team["id"])
            )
            .exclude(action=AuditEntry.Action.CREATED)
            .exists()
        )

    def test_an_approver_cannot_validate_or_activate(self):
        """Approver status is not administrative authority.

        Somebody who can act on a step is not thereby allowed to put teams in
        force; only HR is.
        """
        team = self.create_team()
        self.client.force_authenticate(self.supervisor)
        for url in ("validate", "activate", "deactivate"):
            response = self.client.post(f"{TEAMS_URL}{team['id']}/{url}/", format="json")
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, url
            )


class TeamActivationTests(TeamConfigurationBase):
    """Putting a team into force, and taking it back out."""

    def test_activating_a_valid_team_puts_it_in_force(self):
        team = self.create_team()
        activated = self.activate(team["id"])
        self.assertEqual(activated["status"], Team.Status.ACTIVE)

    def test_activating_dates_the_workflow_it_starts_routing(self):
        """A chain with no start date reads as a draft while it is demonstrably live.

        The team being in force is the decision; dating the chain is what stops
        the two disagreeing about whether this approval path applies.
        """
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        self.assertIsNone(stored.workflow.effective_from)
        self.activate(team["id"])
        stored.refresh_from_db()
        self.assertEqual(stored.workflow.effective_from, timezone.localdate())

    def test_activating_does_not_overwrite_a_workflow_date(self):
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        stored.workflow.effective_from = timezone.localdate() - timedelta(days=5)
        stored.workflow.save(update_fields=["effective_from"])
        self.activate(team["id"])
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.effective_from,
            timezone.localdate() - timedelta(days=5),
        )

    def test_a_draft_team_does_not_route(self):
        team = Team.objects.get(pk=self.create_team()["id"])
        self.place_employee(team)
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("still being set up", str(ctx.exception))

    def test_an_unstaffed_team_cannot_be_activated(self):
        team = self.create_team(
            name="Unstaffed team",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []}
                ]
            },
        )
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).status, Team.Status.DRAFT
        )

    def test_a_refused_activation_returns_every_problem(self):
        team = self.create_team(
            name="Two gaps",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []},
                    {"name": "Head step", "approver_role": "hod", "members": []},
                ]
            },
        )
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(response.data["issues"]), 2)
        self.assertIn("status", response.data)

    def test_a_refused_activation_keeps_the_configuration(self):
        """A refusal is a to-do list, not a discarded draft.

        Throwing away what HR wrote because one step was unstaffed would make
        every failed activation a restart.
        """
        team = self.create_team(
            name="Unstaffed team",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []}
                ]
            },
        )
        self.client.post(f"{TEAMS_URL}{team['id']}/activate/", format="json")
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(stored.workflow.sections.count(), 1)

    def test_activating_is_audited(self):
        team = self.create_team()
        self.activate(team["id"])
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM,
            target_id=str(team["id"]),
            action=AuditEntry.Action.ACTIVATED,
        )
        self.assertEqual(entry.actor, self.hr)
        self.assertEqual(entry.detail["after"]["status"], Team.Status.ACTIVE)

    def test_a_refused_activation_leaves_no_audit_entry(self):
        """A failed action must not leave a phantom record of having happened."""
        team = self.create_team(
            name="Unstaffed team",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []}
                ]
            },
        )
        self.client.post(f"{TEAMS_URL}{team['id']}/activate/", format="json")
        self.assertFalse(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM,
                target_id=str(team["id"]),
                action=AuditEntry.Action.ACTIVATED,
            ).exists()
        )

    def test_activating_twice_is_harmless(self):
        team = self.create_team()
        self.activate(team["id"])
        self.activate(team["id"])
        self.assertEqual(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM,
                target_id=str(team["id"]),
                action=AuditEntry.Action.ACTIVATED,
            ).count(),
            1,
        )

    def test_retiring_stops_new_submissions(self):
        team = self.create_team()
        self.activate(team["id"])
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/deactivate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Team.Status.INACTIVE)

    def test_a_retired_team_cannot_be_reactivated(self):
        """Retiring ends the team; bringing it back means creating it again.

        A configuration that was abandoned — a chain half-swapped, people moved
        elsewhere — should not be able to come back into service by a single
        action, because nothing has re-checked it since.
        """
        team = self.create_team()
        self.activate(team["id"])
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_a_draft_team_cannot_be_retired(self):
        team = self.create_team()
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/deactivate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_retiring_is_audited(self):
        team = self.create_team()
        self.activate(team["id"])
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM,
            target_id=str(team["id"]),
            action=AuditEntry.Action.DEACTIVATED,
        )
        self.assertEqual(entry.detail["after"]["status"], Team.Status.INACTIVE)

    def test_a_team_is_never_hard_deleted(self):
        team = self.create_team()
        self.activate(team["id"])
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        self.assertTrue(Team.objects.filter(pk=team["id"]).exists())

    def test_the_service_refuses_an_invalid_activation_too(self):
        """The action is guarded in the service, not only at the API edge.

        Otherwise a caller reaching the service directly — the admin, a future
        caller, a management command — could put an unstaffed team in force.
        """
        team = self.create_team(
            name="Unstaffed team",
            new_workflow={
                "sections": [
                    {"name": "Supervisor step", "approver_role": "supervisor", "members": []}
                ]
            },
        )
        stored = Team.objects.get(pk=team["id"])
        with self.assertRaises(TeamActionError) as ctx:
            activate_team(team=stored, actor=self.hr)
        stored.refresh_from_db()
        self.assertEqual(stored.status, Team.Status.DRAFT)
        self.assertEqual(ctx.exception.issues[0].code, "no_approver")

    def test_the_service_refuses_to_retire_a_draft(self):
        team = Team.objects.get(pk=self.create_team()["id"])
        with self.assertRaises(TeamActionError):
            deactivate_team(team=team, actor=self.hr)

    def test_an_activated_team_routes_its_employees(self):
        team = self.create_team()
        self.activate(team["id"])
        stored = Team.objects.get(pk=team["id"])
        self.place_employee(stored)
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual([d.role for d in definitions], ["supervisor", "hod"])


class TeamDetailsTests(TeamConfigurationBase):
    """What reading one team back has to answer."""

    def test_the_team_row_carries_its_lifecycle_and_window(self):
        team = self.create_team(
            department="Registrar", effective_from="2026-01-01"
        )
        row = self.read(team["id"])
        self.assertEqual(row["department"], "Registrar")
        self.assertEqual(row["status"], Team.Status.DRAFT)
        self.assertEqual(row["effective_from"], "2026-01-01")
        self.assertTrue(row["is_effective"])

    def test_a_team_outside_its_window_says_so(self):
        team = self.create_team(effective_to="2020-12-31")
        row = self.read(team["id"])
        self.assertFalse(row["is_effective"])

    def test_each_step_reports_who_may_act_and_from_when(self):
        team = self.create_team()
        row = self.read(team["id"])
        first = row["sections"][0]
        self.assertEqual(first["approver_role"], "supervisor")
        self.assertEqual(first["member_count"], 1)
        self.assertEqual(first["members"][0]["user"], self.supervisor.pk)
        self.assertEqual(
            first["members"][0]["effective_from"], str(timezone.localdate())
        )
        self.assertIsNone(first["members"][0]["effective_to"])

    def test_the_flat_member_rollup_names_the_step_each_person_is_on(self):
        team = self.create_team()
        row = self.read(team["id"])
        person = next(m for m in row["members"] if m["user"] == self.hod.pk)
        self.assertEqual(
            [s["name"] for s in person["sections"]], ["Head of Department approval"]
        )
        self.assertEqual([r["code"] for r in person["roles"]], ["hod"])

    def test_a_department_can_be_set_and_changed(self):
        team = self.create_team(department="Registrar")
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/", {"department": "Records"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Team.objects.get(pk=team["id"]).department, "Records")

    def test_the_department_is_trimmed(self):
        team = self.create_team(department="  Registrar  ")
        self.assertEqual(Team.objects.get(pk=team["id"]).department, "Registrar")

    def test_effective_dates_are_audited_with_before_and_after(self):
        team = self.create_team()
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"effective_to": "2026-12-31"},
            format="json",
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM,
            target_id=str(team["id"]),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertEqual(entry.detail["after"]["effective_to"], "2026-12-31")


class MembershipHistoryTests(TeamConfigurationBase):
    """Membership is a period, so "no longer an approver" is a fact, not an absence."""

    def setUp(self):
        super().setUp()
        # People who are *not* already on the chain, so each test is reading the
        # membership it created rather than the fixture's. A section is created
        # with somebody on it, which is what makes these tests about a *change*.
        self.newcomer = make_approver(
            "supervisor", username="new@teamflow.test", institution_wide=False
        )
        self.replacement = make_approver(
            "hod", username="repl@teamflow.test", institution_wide=False
        )
        self.team = Team.objects.get(pk=self.create_team()["id"])
        self.step_one = self.team.workflow.sections.get(order=1)
        self.step_two = self.team.workflow.sections.get(order=2)

    def staff_and_get(self, section: Section, user) -> SectionMember:
        response = self.client.post(
            MEMBERS_URL, {"section": section.pk, "user": user.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return SectionMember.objects.get(section=section, user=user)

    def test_a_membership_records_when_it_began(self):
        self.staff_and_get(self.step_one, self.newcomer)
        self.assertEqual(
            SectionMember.objects.get(
                section=self.step_one, user=self.newcomer
            ).effective_from,
            timezone.localdate(),
        )
        self.assertIsNone(
            SectionMember.objects.get(section=self.step_one, user=self.newcomer).effective_to
        )

    def test_a_membership_may_be_dated_into_the_future(self):
        """HR can hand a step over before the handover date.

        The person starts being eligible when the new period begins rather than
        the moment the row was typed, so nobody is handed an approval they have
        not been told they are responsible for.
        """
        start = timezone.localdate() + timedelta(days=7)
        response = self.client.post(
            MEMBERS_URL,
            {
                "section": self.step_one.pk,
                "user": self.newcomer.pk,
                "effective_from": start.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["effective_from"], start.isoformat())

    def test_a_future_membership_does_not_route_yet(self):
        self.activate(self.team.pk)
        self.place_employee(self.team)
        add_section_member(
            section=self.step_two,
            user=self.replacement,
            actor=self.hr,
            effective_from=timezone.localdate() + timedelta(days=7),
        )
        # Step two's original approver is removed so the only candidate is the
        # one dated into the future; if that counted, the chain would route.
        self.client.delete(
            f"{MEMBERS_URL}"
            f"{SectionMember.objects.get(section=self.step_two, user=self.hod).pk}/"
        )
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("Head of Department", str(ctx.exception))

    def test_removing_a_member_keeps_the_record_of_them(self):
        """The row is closed, not deleted.

        A membership row is a record of who was entitled to act. Deleting it
        would leave an application that somebody with no membership today
        approved with a decision nobody can explain.
        """
        membership = self.staff_and_get(self.step_one, self.newcomer)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertTrue(
            SectionMember.all_objects.filter(pk=membership.pk).exists(),
            "the row is kept as history",
        )
        closed = SectionMember.all_objects.get(pk=membership.pk)
        self.assertEqual(closed.effective_to, timezone.localdate())
        # A period ending today still covers today, so the person can act on what
        # they were already given; it is from tomorrow that they are out. Making
        # removal bite immediately would strand an application sitting at the step
        # they were the only one who could sign.
        self.assertTrue(closed.is_effective())
        self.assertFalse(closed.is_effective(timezone.localdate() + timedelta(days=1)))

    def test_a_closed_membership_is_out_of_the_working_set(self):
        membership = self.staff_and_get(self.step_one, self.newcomer)
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertFalse(
            SectionMember.objects.filter(section=self.step_one, user=self.newcomer).exists()
        )
        self.assertFalse(is_approver_user(self.newcomer))

    def test_a_step_with_a_removed_approver_stops_routing(self):
        self.activate(self.team.pk)
        self.place_employee(self.team)
        membership = SectionMember.objects.get(
            section=self.step_two, user=self.hod
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("Head of Department", str(ctx.exception))

    def test_a_person_can_be_reappointed_after_being_removed(self):
        """Two periods, not a duplicate.

        The uniqueness rule is one *open* membership per section, so a handover
        — remove one person, add another, or the same person again later — is a
        normal thing to be able to do.
        """
        first = self.staff_and_get(self.step_one, self.newcomer)
        self.client.delete(f"{MEMBERS_URL}{first.pk}/")
        second = self.staff_and_get(self.step_one, self.newcomer)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            SectionMember.all_objects.filter(
                section=self.step_one, user=self.newcomer
            ).count(),
            2,
        )
        self.assertTrue(
            SectionMember.objects.filter(section=self.step_one, user=self.newcomer).exists()
        )

    def test_a_duplicate_membership_is_refused_while_one_is_open(self):
        self.staff_and_get(self.step_one, self.newcomer)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.step_one.pk, "user": self.newcomer.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user", response.data)

    def test_a_membership_that_never_took_effect_is_removed_outright(self):
        """A handover that was called off leaves no row claiming it happened."""
        add_section_member(
            section=self.step_one,
            user=self.newcomer,
            actor=self.hr,
            effective_from=timezone.localdate() + timedelta(days=7),
        )
        membership = SectionMember.objects.get(
            section=self.step_one, user=self.newcomer
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertFalse(
            SectionMember.all_objects.filter(
                section=self.step_one, user=self.newcomer
            ).exists()
        )

    def test_the_default_view_is_the_people_who_can_act_now(self):
        """Without asking for history, a member list is a to-do list."""
        self.staff_and_get(self.step_one, self.newcomer)
        response = self.client.get(
            f"{MEMBERS_URL}?section={self.step_one.pk}&user={self.newcomer.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertTrue(response.data["results"][0]["is_effective"])

    def test_history_is_readable_through_the_api(self):
        """Both periods are returned, and they are distinguishable.

        A reappointed person has two rows. The one that ended says when it
        ended; the one that has not says nothing. Neither is hidden, because
        deciding whether somebody was entitled to act on a given date is a
        question the record has to be able to answer.
        """
        first = self.staff_and_get(self.step_one, self.newcomer)
        self.client.delete(f"{MEMBERS_URL}{first.pk}/")
        self.staff_and_get(self.step_one, self.newcomer)

        response = self.client.get(
            f"{MEMBERS_URL}?section={self.step_one.pk}"
            f"&user={self.newcomer.pk}&history=1"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(
            [r["effective_to"] for r in response.data["results"]],
            [timezone.localdate().isoformat(), None],
        )
        # The first period ended today, so it still covers today. Both are in
        # force now; from tomorrow only the second is.
        self.assertEqual(
            [r["is_effective"] for r in response.data["results"]], [True, True]
        )

    def test_an_end_date_before_the_start_date_is_refused(self):
        add_section_member(
            section=self.step_one,
            user=self.newcomer,
            actor=self.hr,
            effective_from=timezone.localdate() + timedelta(days=7),
        )
        membership = SectionMember.objects.get(
            section=self.step_one, user=self.newcomer
        )
        with self.assertRaises(TeamActionError):
            remove_section_member(
                membership=membership,
                actor=self.hr,
                effective_to=timezone.localdate(),
            )


class TeamRoutingTests(TeamConfigurationBase, StubProviderMixin):
    """The employee's side: which team's chain an application follows."""

    def setUp(self):
        # The rules provider is stubbed so dates are predictable; the *workflow*
        # provider is the real one, because the team's configuration is exactly
        # what is under test.
        self.stub = self.use_stub()
        self.use_real_workflow_provider()
        super().setUp()
        self.stub.register_employee(self.employee)

    def submit(self, start_offset: int = 30):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=ANNUAL_START + timedelta(days=start_offset),
            end_date=ANNUAL_START + timedelta(days=start_offset + 3),
            reason="Family visit",
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def test_an_application_follows_its_team(self):
        team = self.create_team()
        self.activate(team["id"])
        self.place_employee(Team.objects.get(pk=team["id"]))
        app = self.submit()
        self.assertEqual(
            [s.role for s in app.stages.order_by("stage_order")],
            ["supervisor", "hod"],
        )

    def test_a_step_a_live_application_is_waiting_on_cannot_be_removed(self):
        """Editing the steps must not rewrite the past.

        An application already sitting at a step has that step snapshotted onto
        its stage, and the stage still points at the section. Dropping the step
        in the team form would leave that application with nowhere to go, so the
        database refuses and the edit comes back as a validation error rather
        than as an application that can never advance.
        """
        team = self.create_team()
        self.activate(team["id"])
        self.place_employee(Team.objects.get(pk=team["id"]))
        app = self.submit()
        pending = app.stages.get(status=ApplicationStage.Status.PENDING)

        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Head of Department approval",
                            "approver_role": "hod",
                        }
                    ]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(
            [
                s.approver_role.code
                for s in Team.objects.get(pk=team["id"]).workflow.sections.order_by("order")
            ],
            ["supervisor", "hod"],
        )
        pending.refresh_from_db()
        self.assertEqual(pending.status, ApplicationStage.Status.PENDING)

    def test_a_step_an_application_has_already_passed_through_cannot_be_removed(self):
        """Once a step has been used, it stays on the chain.

        Every stage keeps a pointer to the step it was materialised from, so
        "which step was this decided at" is still answerable years later. A
        decided stage is no exception: the application is finished, but the
        record of how it got there is not, and the step is what that record
        points at. So a chain that has carried an application cannot be
        trimmed — only re-pointed, by changing a step rather than removing it.
        """
        team = self.create_team()
        self.activate(team["id"])
        self.place_employee(Team.objects.get(pk=team["id"]))
        app = self.submit()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Head of Department approval",
                            "approver_role": "hod",
                        }
                    ]
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("Supervisor approval", str(response.data))
        self.assertEqual(
            [
                s.approver_role.code
                for s in Team.objects.get(pk=team["id"]).workflow.sections.order_by("order")
            ],
            ["supervisor", "hod"],
        )

    def test_a_step_no_application_has_used_can_be_removed(self):
        """Refusing forever would make the form unable to tidy up a chain.

        A step that nothing was ever submitted against has no history to lose,
        so removing it is the HR correcting their own configuration, and the
        team form has to allow it.
        """
        team = self.create_team(
            new_workflow={
                "sections": [
                    *self.chain,
                    {"name": "Registrar step", "approver_role": "registrar"},
                ]
            }
        )
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"new_workflow": {"sections": self.chain}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            [
                s.approver_role.code
                for s in Team.objects.get(pk=team["id"]).workflow.sections.order_by("order")
            ],
            ["supervisor", "hod"],
        )

    def test_a_draft_team_refuses_the_submission_and_names_the_team(self):
        """The failure arrives before the employee loses anything.

        ``workflow_unavailable`` at submission is the whole reason a draft team
        is harmless: the employee is told to ask HR, not handed a chain that
        stalls at a step with nobody on it.
        """
        team = self.create_team()
        self.place_employee(Team.objects.get(pk=team["id"]))
        with self.assertRaises(ValidationFailedError) as ctx:
            self.submit()
        self.assertEqual(
            [i.code for i in ctx.exception.errors], ["workflow_unavailable"]
        )
        self.assertIn("Administration team", str(ctx.exception))

    def test_an_unstaffed_step_refuses_the_submission_by_name(self):
        """A step can be staffed when it is configured and not later.

        So the honest way to reach this state is a handover: activate the team
        with somebody on the step, then take them off it. The applicant's failure
        has to name the step and the role, because "your application cannot be
        submitted" with no reason sends them to the wrong desk.
        """
        team = self.create_team(name="Gap team")
        self.activate(team["id"])
        stored = Team.objects.get(pk=team["id"])
        self.place_employee(stored)
        membership = SectionMember.objects.get(
            section=stored.workflow.sections.get(order=2), user=self.hod
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        with self.assertRaises(ValidationFailedError) as ctx:
            self.submit()
        self.assertIn("Head of Department", str(ctx.exception))

    def test_a_team_outside_its_window_refuses_the_submission(self):
        team = self.create_team(
            name="Windowed team",
            effective_from=ANNUAL_START + timedelta(days=200),
        )
        self.activate(team["id"])
        self.place_employee(Team.objects.get(pk=team["id"]))
        with self.assertRaises(ValidationFailedError) as ctx:
            self.submit()
        self.assertIn("does not start until", str(ctx.exception))


class HistoricalIntegrityTests(TeamConfigurationBase, StubProviderMixin):
    """What an in-flight application keeps, whatever HR does to the team after.

    These are the tests for the reason the whole configuration is snapshotted:
    an application must be judged by the chain it was submitted against, not by
    whatever the team looks like when somebody gets round to approving it.
    """

    def setUp(self):
        self.stub = self.use_stub()
        self.use_real_workflow_provider()
        super().setUp()
        self.stub.register_employee(self.employee)
        self.team = self.create_team(name="Administration team")
        self.activate(self.team["id"])
        self.stored = Team.objects.get(pk=self.team["id"])
        self.place_employee(self.stored)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=ANNUAL_START,
            end_date=ANNUAL_START + timedelta(days=3),
            reason="Family visit",
        )
        self.app = submit_application(user=self.employee, application_id=app.pk)

    def test_retiring_the_team_leaves_the_application_decidable(self):
        """Retirement stops new submissions; it does not abandon live ones."""
        self.client.post(f"{TEAMS_URL}{self.team['id']}/deactivate/", format="json")
        self.assertEqual(
            set(
                self.app.current_stage.eligible_approvers.values_list(
                    "user_id", flat=True
                )
            ),
            {self.supervisor.pk},
        )

    def test_removing_the_approver_leaves_the_application_decidable(self):
        """The eligibility snapshot is the authority for a live application.

        A membership that ends today cannot un-approve an application that was
        materialised yesterday: the person who was on the step when it was
        submitted is who may decide it, and the stage snapshot is what proves
        that later.
        """
        membership = SectionMember.objects.get(
            section=self.stored.workflow.sections.get(order=1),
            user=self.supervisor,
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertFalse(is_approver_user(self.supervisor))
        self.assertEqual(
            set(
                self.app.current_stage.eligible_approvers.values_list(
                    "user_id", flat=True
                )
            ),
            {self.supervisor.pk},
        )

    def test_the_removed_approver_can_still_decide_the_live_application(self):
        """The end of a membership is not a retraction of what came before."""
        membership = SectionMember.objects.get(
            section=self.stored.workflow.sections.get(order=1),
            user=self.supervisor,
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        decide(
            application_id=self.app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=1,
        )
        self.app.refresh_from_db()
        self.assertEqual(
            self.app.current_stage.stage_order, 2
        )

    def test_a_new_application_after_a_membership_change_uses_the_new_roster(self):
        """The snapshot is per application, not a permanent freeze."""
        replacement = make_approver(
            "supervisor", username="sup2@teamflow.test", institution_wide=False
        )
        membership = SectionMember.objects.get(
            section=self.stored.workflow.sections.get(order=1),
            user=self.supervisor,
        )
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(
            self.client.post(
                MEMBERS_URL,
                {
                    "section": self.stored.workflow.sections.get(order=1).pk,
                    "user": replacement.pk,
                },
                format="json",
            ).status_code,
            status.HTTP_201_CREATED,
        )

        EmployeeProfile.objects.filter(user=self.employee).update(team=self.stored)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=ANNUAL_START + timedelta(days=30),
            end_date=ANNUAL_START + timedelta(days=33),
            reason="Family visit",
        )
        fresh = submit_application(user=self.employee, application_id=app.pk)
        self.assertEqual(
            set(
                fresh.current_stage.eligible_approvers.values_list("user_id", flat=True)
            ),
            {replacement.pk},
        )
        # And the original is untouched.
        self.assertEqual(
            set(
                self.app.current_stage.eligible_approvers.values_list("user_id", flat=True)
            ),
            {self.supervisor.pk},
        )

    def test_the_stage_snapshots_name_the_role_and_step_it_came_from(self):
        """A stage is readable years later without resolving anything live."""
        stage = self.app.stages.order_by("stage_order").first()
        self.assertEqual(stage.role, "supervisor")
        self.assertEqual(stage.role_label, "Supervisor")
        self.assertEqual(
            stage.section_ref_id,
            self.stored.workflow.sections.get(order=1).pk,
        )

    def test_a_section_a_live_stage_points_at_cannot_be_deleted(self):
        """Rebuilding a chain must not be able to pull the rug from under it.

        The stage points at the section it came from with a protected foreign
        key, so while an application is waiting there the row cannot be deleted
        out from under it, and the stage keeps its own copy of the step's meaning
        rather than having to go and look it up.
        """
        section = self.stored.workflow.sections.get(order=1)
        with self.assertRaises(ProtectedError):
            section.delete()

        stage = self.app.stages.get(stage_order=1)
        self.assertEqual(stage.section_ref_id, section.pk)
        self.assertEqual(stage.role, "supervisor")
        self.assertEqual(stage.role_label, "Supervisor")
        self.assertEqual(
            set(stage.eligible_approvers.values_list("user_id", flat=True)),
            {self.supervisor.pk},
        )


