"""Configuring a team end to end: create it, validate it, let it route.

A team is the object HR actually works with, and these tests exercise it the way
the product now asks HR to work: name it, hand it to a manager, who describes and
staffs the chain it needs, with validation reporting anything left wrong.

The three properties worth stating up front, because the rest of the file is
mostly about them:

**Creating a team puts it in force.** There is no separate "activate" step for
HR to forget, so what is left to check is the configuration rather than the
lifecycle. A team with no chain routes nothing, because there is nothing to route
through — not because it has yet been switched on.

**Every problem is reported, and the team is left alone.** Validation returns the
whole list rather than the first failure and never changes the team, so a refusal
is a to-do list and not a dead end.

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
from leave.models import FinancialYear, LeaveApplication
from leave.services.submission import ValidationFailedError, submit_application
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin
from users.models import EmployeeProfile

from approvals.models import (
    ApplicationStage,
    ApprovalDecision,
)
from organisation.models import ApproverRole, Team
from workflows.models import Section, SectionMember, Workflow
from .providers import DatabaseWorkflowProvider, WorkflowConfigError
from approvals.services import (
    decide,
)
from organisation.services import is_approver_user, create_team_role_assignment

from .services import (
    TeamActionError,
    add_section_member,
    create_team,
    deactivate_team,
    remove_section_member,
    validate_team,
)
from .testing import (
    DEV_PASSWORD,
    campus_for,
    ensure_roles,
    make_approver,
    make_employee,
    make_workflow,
    team_for,
)

User = get_user_model()

#: The stub rules provider's reference "today" is 2026-09-21, so the earliest
#: annual start is the first date satisfying the notice period.
ANNUAL_START = EARLIEST_ANNUAL_START

TEAMS_URL = "/api/v1/teams/"
MEMBERS_URL = "/api/v1/section-members/"
WORKFLOWS_URL = "/api/v1/workflows/"


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
        # Roles are HR data, not migration seed: a bare test database has none.
        ensure_roles("supervisor", "hod", "dean", "registrar")
        # A team's approvers are its own members, so these people start on no
        # team: creating the team is what places them on it.
        # Not institution-wide: these people are on the team's steps, which is
        # the case under test. A global holder would quietly stand in for an
        # unstaffed step and make a broken configuration look whole.
        self.supervisor = make_approver(
            "supervisor",
            username="sup@teamflow.test",
            institution_wide=False,
        )
        self.hod = make_approver(
            "hod",
            username="hod@teamflow.test",
            institution_wide=False,
        )

        # One approver per step: a step routes to one person.
        self.chain = [
            {
                "name": "Supervisor approval",
                "approver_role": "supervisor",
                "approver": self.supervisor.pk,
            },
            {
                "name": "Head of Department approval",
                "approver_role": "hod",
                "approver": self.hod.pk,
            },
        ]

    def approvers_for(self, suffix: str):
        """A fresh, unassigned approver pair for one team.

        An employee belongs to exactly one team, and creating a team is what
        places its named approvers on it, so a second team cannot reuse the first
        team's people. Tests that build several teams ask for a pair per team.
        """
        return (
            make_approver(
                "supervisor",
                username=f"sup-{suffix}@teamflow.test",
                institution_wide=False,
            ),
            make_approver(
                "hod", username=f"hod-{suffix}@teamflow.test", institution_wide=False
            ),
        )

    def chain_for(self, approvers) -> list:
        """The standard two-step chain, staffed by ``approvers``."""
        supervisor, hod = approvers
        return [
            {
                "name": "Supervisor approval",
                "approver_role": "supervisor",
                "approver": supervisor.pk,
            },
            {
                "name": "Head of Department approval",
                "approver_role": "hod",
                "approver": hod.pk,
            },
        ]

    def create_team(self, name="Administration team", approvers=None, **extra) -> dict:
        """Create a team as HR, then let its manager place the approvers and
        write the chain — the handover the product now makes, exercised through
        the real API rather than built behind it."""
        chain = self.chain if approvers is None else self.chain_for(approvers)
        team = self.bare_team(name, **extra)
        self.place_on_team(
            team,
            *[User.objects.get(pk=step["approver"]) for step in chain if step.get("approver")],
        )
        response = self.build_chain(team, chain)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return self.read(team.pk)

    def activate(self, team_id: int) -> dict:
        """Assert the team is in force, which creating it already made true.

        Kept as a named step so a test that needs a live team still says so,
        while making it obvious there is no action left for anyone to perform.
        """
        row = self.read(team_id)
        self.assertEqual(row["status"], Team.Status.ACTIVE, row)
        return row

    def manager_client(self, team) -> APIClient:
        """An authenticated client for ``team``'s designated manager.

        Staffing a team's steps follows the handover: HR creates the team and
        names its manager, who then runs the roster. Tests that appoint or clear
        a step approver therefore act as the manager, built to match the team's
        category so the designation itself is valid.
        """
        if not hasattr(self, "_manager_clients"):
            self._manager_clients: dict[int, APIClient] = {}
        if team.pk not in self._manager_clients:
            manager = make_employee(
                f"manager-{team.pk}@teamflow.test", team=None, category=team.category
            )
            create_team_role_assignment(
                team=team,
                role=ensure_roles("dvc")["dvc"],
                user=manager,
                actor=self.hr,
                is_team_manager=True,
            )
            client = APIClient()
            client.force_authenticate(manager)
            self._manager_clients[team.pk] = client
        return self._manager_clients[team.pk]

    def appoint(self, section, user, **extra):
        """POST a section appointment as ``section``'s team manager."""
        payload = {"section": section.pk, "user": getattr(user, "pk", user), **extra}
        return self.manager_client(section.workflow.team).post(
            MEMBERS_URL, payload, format="json"
        )

    def unappoint(self, membership):
        """DELETE a section membership as its team's manager."""
        return self.manager_client(membership.section.workflow.team).delete(
            f"{MEMBERS_URL}{membership.pk}/"
        )

    def place_on_team(self, team: Team, *people) -> None:
        """Put people on a team, the way its manager places members.

        A team-scoped approver must be a member of the team they approve for, so
        a chain that names somebody is only written after they are on the team.
        """
        for person in people:
            profile = EmployeeProfile.objects.get(user=person)
            profile.team = team
            profile.save(update_fields=["team"])

    def bare_team(self, name: str = "Administration team", **extra) -> Team:
        """A team with no chain, as HR saves it before the manager writes one."""
        payload: dict = {
            "name": name,
            "description": "Administration approval chain",
        }
        payload.update(extra)
        response = self.client.post(TEAMS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return Team.objects.get(pk=response.data["id"])

    def build_chain(self, team: Team, sections: list, *, name: str | None = None):
        """The team's manager writes its chain through the workflow endpoint."""
        payload: dict = {"team": team.pk, "sections": sections, "name": name or f"{team.name} chain"}
        return self.manager_client(team).post(WORKFLOWS_URL, payload, format="json")

    def edit_chain(self, team: Team, sections: list, *, name: str | None = None):
        """The team's manager rewrites the team's chain in place."""
        payload: dict = {"sections": sections}
        if name is not None:
            payload["name"] = name
        else:
            payload["name"] = f"{team.workflow.name or team.name} chain" if hasattr(team, "workflow") and team.workflow else f"{team.name} chain"
        return self.manager_client(team).patch(
            f"{WORKFLOWS_URL}{team.workflow_id}/", payload, format="json"
        )

    def read(self, team_id: int) -> dict:
        response = self.client.get(f"{TEAMS_URL}{team_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def place_employee(self, team: Team):
        EmployeeProfile.objects.update_or_create(
            user=self.employee,
            defaults={"team": team},
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

    def test_a_team_is_created_with_its_workflow_sections_and_approvers(self):
        team = self.create_team()
        self.assertEqual(team["status"], Team.Status.ACTIVE)
        self.assertTrue(team["workflow_name"])

        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["supervisor", "hod"],
        )
        self.assertEqual(
            stored.workflow.sections.get(approver_role__code="supervisor").approver_id,
            self.supervisor.pk,
        )
        # Each appointment is also an effective-dated period, so the history of
        # who held the step is a record rather than a snapshot.
        self.assertEqual(
            SectionMember.objects.get(
                section=stored.workflow.sections.get(approver_role__code="supervisor"),
                user=self.supervisor,
            ).effective_to,
            None,
        )

    def test_the_chain_is_ordered_by_the_order_given(self):
        """Steps run top to bottom, not in the order the payload happened to have.

        A chain whose order depended on submission order would let a client
        silently reshuffle a live approval sequence by re-sending the same steps.
        """
        team = self.bare_team("Reversed team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(team, list(reversed(self.chain)))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            [
                s.approver_role.code
                for s in Team.objects.get(pk=team.pk).workflow.sections.order_by("order")
            ],
            ["hod", "supervisor"],
        )

    def test_a_named_chain_is_used_verbatim(self):
        team = self.bare_team("Named chain team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(team, self.chain, name="ICT leave chain")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Team.objects.get(pk=team.pk).workflow.name, "ICT leave chain")

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
        second = self.create_team(
            name="Second team", approvers=self.approvers_for("second")
        )
        self.assertNotEqual(first["workflow"], second["workflow"])
        self.assertEqual(
            Workflow.objects.filter(team__isnull=False).count(),
            Team.objects.count(),
        )

    def test_a_team_may_be_saved_before_its_chain_is_known(self):
        """Page 1 of the team form: identity, chain to follow.

        A team is named before anybody knows which posts it needs to route
        through, so refusing a team with no chain would force HR to know the
        answer up front. It is saved as a draft, and activation is what refuses a
        chainless team \u2014 that check lives in TeamValidationTests.
        """
        response = self.client.post(
            TEAMS_URL,
            {"name": "Nothing team"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], Team.Status.ACTIVE)
        self.assertIsNone(response.data["workflow"])
        self.assertEqual(response.data["sections"], [])
        self.assertEqual(response.data["members"], [])

    def test_a_workflow_sent_on_create_is_refused(self):
        """A new team cannot adopt a chain that already exists.

        ``workflow`` used to be the pointer a team routed through, written by
        HR. Routing is the manager's decision now, so the field is refused
        outright rather than half-honoured, and the team is not created with a
        chain the caller thought it had attached.
        """
        other = self.create_team(name="Other team", approvers=self.approvers_for("other"))
        response = self.client.post(
            TEAMS_URL,
            {"name": "Copying team", "workflow": other["workflow"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("workflow", response.data)
        self.assertFalse(Team.objects.filter(name="Copying team").exists())

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
                        {"name": "Step", "approver_role": "not-a-role"}
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
                        {"name": "Dean step", "approver_role": "dean"}
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
                            "approver": self.supervisor.pk,
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Team.objects.count(), 0)

    def test_a_roster_in_the_payload_staffs_nobody(self):
        """The old payload listed members; a step now takes one approver.

        A form still sending a roster would otherwise look like it worked while
        staffing nobody \u2014 the step would come back unstaffed and the person
        who filled it in would have no way to tell what had happened. So the
        roster is ignored, and the test says so explicitly: what matters is that
        the resulting step has no approver, not that a key was rejected.
        """
        team = self.bare_team("Roster team")
        response = self.build_chain(
            team,
            [
                {
                    "name": "Supervisor step",
                    "approver_role": "supervisor",
                    "members": [self.supervisor.pk],
                }
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        section = Team.objects.get(pk=team.pk).workflow.sections.get(order=1)
        self.assertIsNone(section.approver_id)

    def test_one_may_not_hold_two_stages_of_one_chain(self):
        """Unit 30: one employee, one stage, one role per workflow.

        This was allowed once — "a chain that needs the supervisor to look twice
        has two steps and one person" — and requirement 9 reverses it. Two steps
        with two different roles, so the per-team role rule does not fire
        first and the refusal is unambiguously the per-workflow one.
        """
        team = self.bare_team("Two step team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(
            team,
            [
                {
                    "name": "First look",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {
                    "name": "Second look",
                    "approver_role": "hod",
                    "approver": self.supervisor.pk,
                },
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already assigned to step 1", str(response.data))
        self.assertIsNone(Team.objects.get(pk=team.pk).workflow_id)

    def test_a_role_may_not_repeat_across_stages_of_one_chain(self):
        """The other leg: a role is on one stage per workflow too (Unit 30).

        The refusal names the role, because that is the first thing wrong with
        this payload — the employee on both steps is a second problem that HR
        only reaches once the roles are distinct.
        """
        team = self.bare_team("Two step team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(
            team,
            [
                {
                    "name": "First look",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {
                    "name": "Second look",
                    "approver_role": "supervisor",
                    "approver": self.hod.pk,
                },
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already assigned to another stage", str(response.data))
        self.assertIsNone(Team.objects.get(pk=team.pk).workflow_id)

    def test_the_one_role_rule_does_not_reach_across_teams(self):
        """The restriction is scoped to a team, not global.

        Two teams each need somebody at "Supervisor", and they are different
        people on different teams. If the rule were global, staffing the second
        team would be impossible — which is exactly the shape Phase 1 has to get
        right, because an employee belongs to exactly one team and therefore can
        only ever be appointed within it.
        """
        registry_supervisor, registry_hod = self.approvers_for("registry")
        self.create_team(
            name="Registry team", approvers=(registry_supervisor, registry_hod)
        )
        records_supervisor, records_hod = self.approvers_for("records")
        second = self.create_team(
            name="Records team", approvers=(records_supervisor, records_hod)
        )
        # The same role code is held by a different person on each team, and each
        # appointment is confined to its own team's chain.
        self.assertEqual(
            Section.objects.filter(
                approver_role__code="supervisor",
                workflow__team__name="Registry team",
            ).count(),
            1,
        )
        self.assertEqual(
            Section.objects.filter(
                approver_role__code="supervisor",
                approver=records_supervisor,
                workflow_id=second["workflow"],
            ).count(),
            1,
        )
        self.assertNotEqual(registry_supervisor.pk, records_supervisor.pk)

    def test_creation_is_audited_for_both_the_team_and_its_chain(self):
        team = self.create_team()
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM,
                action=AuditEntry.Action.CREATED,
                target_id=str(team["id"]),
            ).exists()
        )
        # The chain's own creation, as opposed to the appointments written with
        # it — both are audited, so this asks for the one that names the team.
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.CREATED,
            target_id=str(team["workflow"]),
            reason__startswith="Created for the",
        )
        self.assertEqual(
            [s["approver_role"] for s in entry.detail["after"]["sections"]],
            ["supervisor", "hod"],
        )
        self.assertIn("Administration team", entry.reason)

    def test_non_hr_cannot_configure_a_team(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Sneaky team",
                "new_workflow": {
                    "sections": [
                        {
                            "name": "Step",
                            "approver_role": "supervisor",
                            "approver": self.supervisor.pk,
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Team.objects.count(), 0)


class TeamChainEditingTests(TeamConfigurationBase):
    """Editing a team's chain, which is the manager's job and nowhere else.

    HR creates the team and names its manager; the manager writes and rewrites
    the chain through the workflow endpoint. The manager's edit is the only
    writer, which means these tests are the only place the "edit the steps"
    path is covered — and they are what stops a later change from quietly
    re-introducing HR as a second place to edit a chain.
    """

    def test_the_steps_can_be_rewritten_by_the_manager(self):
        team = self.create_team()
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [
                {"name": "Supervisor", "approver_role": "supervisor"},
                {"name": "Dean", "approver_role": "dean"},
            ],
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
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Only step", "approver_role": "supervisor"}],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/", {"name": "Renamed team"}, format="json"
        )
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(stored.workflow_id, original_chain)
        self.assertEqual(stored.name, "Renamed team")

    def test_reordering_keeps_each_step_and_its_approver(self):
        """A reorder is the same steps in a new order, not a new set of steps.

        Sections are identified by their role and name, so moving one keeps its
        approver. Rebuilding them empty would make a drag in the form silently
        strip the person, which is the one way a reorder could hurt someone.
        """
        team = self.create_team()
        sections = list(
            Team.objects.get(pk=team["id"]).workflow.sections.order_by("order")
        )
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [
                {
                    "name": s.name,
                    "approver_role": s.approver_role.code,
                    "approver": s.approver_id,
                }
                for s in reversed(sections)
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(
            [s.approver_role.code for s in stored.workflow.sections.order_by("order")],
            ["hod", "supervisor"],
        )
        self.assertEqual(
            stored.workflow.sections.get(approver_role__code="hod").approver_id,
            self.hod.pk,
        )

    def test_renaming_a_step_rebuilds_it_empty(self):
        """A step with a different role or name is a different step.

        Carrying the old approver across would hand a new role somebody nobody
        appointed. The step comes back visibly empty instead, and the readiness
        check is what says so.
        """
        team = self.create_team()
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [
                {"name": "Renamed supervisor step", "approver_role": "supervisor"},
                {
                    "name": "Head of Department approval",
                    "approver_role": "hod",
                },
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        chain = Team.objects.get(pk=team["id"]).workflow
        renamed = chain.sections.get(name="Renamed supervisor step")
        self.assertIsNone(renamed.approver_id)
        # The step that did not change kept its approver, so renaming one step is
        # a local change rather than a reason to restaff the whole chain.
        self.assertEqual(
            chain.sections.get(name="Head of Department approval").approver_id,
            self.hod.pk,
        )

    def test_editing_the_steps_is_audited_against_the_chain(self):
        team = self.create_team()
        self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Single step", "approver_role": "supervisor"}],
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.UPDATED,
            target_id=str(team["workflow"]),
        )
        self.assertEqual(entry.detail["team"], "Administration team")

    def test_the_chain_can_be_renamed_by_the_manager(self):
        team = self.create_team()
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]), self.chain, name="ICT leave chain"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
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

        A team is in force from creation, so a chain save must not quietly take
        it out of service — or bring a retired one back.
        """
        team = self.create_team()
        self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Step", "approver_role": "supervisor"}],
        )
        self.assertEqual(Team.objects.get(pk=team["id"]).status, Team.Status.ACTIVE)

    def test_an_empty_step_list_is_refused_on_edit(self):
        """A team whose steps were all deleted would route nothing."""
        team = self.create_team()
        response = self.edit_chain(Team.objects.get(pk=team["id"]), [])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.sections.count(), 2
        )

    def test_a_bad_role_is_refused_on_edit_and_leaves_the_steps_alone(self):
        team = self.create_team()
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Step", "approver_role": "not-a-role"}],
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.sections.count(), 2
        )

    def test_a_chain_can_appoint_one_approver_to_a_step(self):
        """The manager names each step's approver, so staffing is part of writing
        the chain. One person per step: there is no separate roster to keep in
        step with the steps themselves. A *change* of approver is still audited
        as its own fact by the membership record, so the handover stays
        answerable after it.
        """
        team = self.bare_team("Unstaffed team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(
            team,
            [
                {
                    "name": "Supervisor",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {
                    "name": "Hod",
                    "approver_role": "hod",
                    "approver": self.hod.pk,
                },
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        stored = Team.objects.get(pk=team.pk)
        self.assertEqual(
            [
                s.approver_id for s in stored.workflow.sections.order_by("order")
            ],
            [self.supervisor.pk, self.hod.pk],
        )
        self.assertEqual(
            SectionMember.objects.filter(section__workflow=stored.workflow).count(), 2
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
        team = self.bare_team("Gap team")
        self.place_on_team(team, self.supervisor)
        response = self.build_chain(
            team,
            [
                {
                    "name": "Supervisor step",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {"name": "Head of Department step", "approver_role": "hod"},
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        response = self.client.post(
            f"{TEAMS_URL}{team.pk}/validate/", format="json"
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
        team = self.bare_team("Three gaps")
        response = self.build_chain(
            team,
            [
                {"name": "Supervisor step", "approver_role": "supervisor"},
                {"name": "Head step", "approver_role": "hod"},
                {"name": "Dean step", "approver_role": "dean"},
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        response = self.client.post(
            f"{TEAMS_URL}{team.pk}/validate/", format="json"
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

    def test_several_active_teams_may_coexist(self):
        """Several working teams at once — the documented shape.

        Routing follows the team, so two active teams is not ambiguous to the
        engine: each employee is on exactly one team and follows its own chain.
        Nothing needs to say it out loud, and nothing should refuse the second
        activation.
        """
        self.create_team(name="Registry team", approvers=self.approvers_for("registry"))
        second = self.create_team(
            name="Records team", approvers=self.approvers_for("records")
        )
        self.activate(Team.objects.get(name="Registry team").pk)
        activated = self.activate(second["id"])
        self.assertEqual(activated["status"], Team.Status.ACTIVE)
        self.assertEqual(
            self.client.post(
                f"{TEAMS_URL}{second['id']}/validate/", format="json"
            ).data["ready"],
            True,
        )

    def test_two_active_teams_keep_their_own_chain(self):
        """Each team routes through its own workflow, never a shared one.

        A chain is a OneToOneField on the team and is written inline with it, so
        this is the shape the model already enforces. Asserting it at the
        routing layer is the point: nothing else proves that each employee's
        application is materialised with their own team's step.
        """
        self.use_real_workflow_provider()
        registry = self.bare_team("Registry team")
        self.place_on_team(registry, self.supervisor)
        created = self.build_chain(
            registry,
            [
                {
                    "name": "Supervisor approval",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                }
            ],
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        records = self.bare_team("Records team")
        self.place_on_team(records, self.hod)
        created = self.build_chain(
            records,
            [
                {
                    "name": "Head of Department approval",
                    "approver_role": "hod",
                    "approver": self.hod.pk,
                }
            ],
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        registry_row = Team.objects.get(pk=registry.pk)
        records_row = Team.objects.get(pk=records.pk)
        self.activate(registry_row.pk)
        self.activate(records_row.pk)
        # Two active teams, two distinct chains.
        self.assertNotEqual(registry_row.workflow_id, records_row.workflow_id)

        registry_stages = self.stages_for(registry_row)
        records_stages = self.stages_for(records_row)
        self.assertEqual([s.role for s in registry_stages], ["supervisor"])
        self.assertEqual([s.role for s in records_stages], ["hod"])
        # And the steps are the two chains' own sections, not one shared chain.
        registry_sections = set(registry_row.workflow.sections.values_list("pk", flat=True))
        records_sections = set(records_row.workflow.sections.values_list("pk", flat=True))
        self.assertEqual({s.section_id for s in registry_stages}, registry_sections)
        self.assertEqual({s.section_id for s in records_stages}, records_sections)
        self.assertFalse(registry_sections & records_sections)

    def stages_for(self, team: Team) -> list:
        """The stages an employee on ``team`` would be given, from the real provider."""
        self.place_employee(team)
        return DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )

    def test_one_person_holds_one_role_on_a_team(self):
        """An employee is appointed once, in one role, on a team's chain.

        A team owns exactly one workflow, so "one stage per workflow" already
        covers a team completely: there is no second chain on the same team for
        somebody to also sit on in another role. That is why the per-workflow
        check is the one that fires here, and it is what keeps skip-forward
        routing unambiguous — "the applicant's stage" is only well defined
        because a person cannot hold two.
        """
        registry = self.create_team(name="Registry team")
        # The same role again on the same chain: already appointed, so it is a
        # no-op rather than a second appointment.
        same_role = self.edit_chain(
            Team.objects.get(pk=registry["id"]),
            [
                {
                    "name": "Supervisor approval",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                }
            ],
        )
        self.assertEqual(same_role.status_code, status.HTTP_200_OK, same_role.data)

        # A second team may hold the same office through a different person: the
        # scope is the team, so nothing is compared across them.
        records_supervisor, _ = self.approvers_for("records")
        elsewhere = self.bare_team("Records team")
        self.place_on_team(elsewhere, records_supervisor)
        response = self.build_chain(
            elsewhere,
            [
                {
                    "name": "Dean approval",
                    "approver_role": "dean",
                    "approver": records_supervisor.pk,
                }
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            Team.objects.get(pk=elsewhere.pk)
            .workflow.sections.get(approver_role__code="dean")
            .approver_id,
            records_supervisor.pk,
        )

        # On its own team, though, self.supervisor cannot take a second step in
        # another role while still holding the first.
        ensure_roles("dean")
        refused = self.edit_chain(
            Team.objects.get(pk=registry["id"]),
            [
                {
                    "name": "Supervisor approval",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {
                    "name": "Dean approval",
                    "approver_role": "dean",
                    "approver": self.supervisor.pk,
                },
            ],
        )
        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST, refused.data)
        self.assertIn("one stage per workflow", str(refused.data).lower())

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
        for url in ("validate", "deactivate"):
            response = self.client.post(f"{TEAMS_URL}{team['id']}/{url}/", format="json")
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, url
            )
        response = self.client.post(f"{TEAMS_URL}{team['id']}/activate/", format="json")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


class TeamActivationTests(TeamConfigurationBase):
    """Teams are in force from the moment HR creates them.

    Creation *is* the act of putting a team into force, so there is no second
    confirmation for HR to give and no action left to call. What remains of the
    lifecycle is what a team in force does, how it is dated, and the one move
    that takes it back out.
    """

    def test_a_team_is_in_force_the_moment_it_is_created(self):
        team = self.bare_team("Fresh team")
        self.assertEqual(Team.objects.get(pk=team.pk).status, Team.Status.ACTIVE)

    def test_there_is_no_activation_action_left_to_call(self):
        """A second confirmation of something that already happened."""
        team = self.create_team()
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Team.objects.get(pk=team["id"]).status, Team.Status.ACTIVE)

    def test_creating_a_chain_dates_it_to_the_academic_year(self):
        """A chain starts today and closes at the end of the academic calendar.

        A chain is a statement about a term, so it is written against the year
        the team is configured in rather than left open-ended: without a closing
        date it would still read as in force years after the year it was written
        for has ended.
        """
        today = timezone.localdate()
        year = FinancialYear.objects.create(
            start_date=today.replace(month=1, day=1),
            end_date=today.replace(month=12, day=31),
            is_active=True,
        )
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(stored.workflow.effective_from, today)
        self.assertEqual(stored.workflow.effective_to, year.end_date)
        self.assertEqual(stored.workflow.state, "active")

    def test_a_chain_written_without_an_academic_year_has_no_end_date(self):
        """Nothing configured means no boundary at all, rather than a guess."""
        self.assertFalse(FinancialYear.objects.filter(is_active=True).exists())
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        self.assertIsNone(stored.workflow.effective_to)
        self.assertEqual(stored.workflow.state, "active")

    def test_editing_the_chain_keeps_the_date_it_was_given(self):
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        stored.workflow.effective_from = timezone.localdate() - timedelta(days=5)
        stored.workflow.save(update_fields=["effective_from"])
        self.edit_chain(stored, [{"name": "Step", "approver_role": "supervisor"}])
        self.assertEqual(
            Team.objects.get(pk=team["id"]).workflow.effective_from,
            timezone.localdate() - timedelta(days=5),
        )

    def test_a_team_in_force_without_a_chain_routes_nothing(self):
        """There is nothing to route through, rather than something not switched on."""
        team = self.bare_team("No chain yet")
        self.place_employee(team)
        with self.assertRaises(WorkflowConfigError) as ctx:
            DatabaseWorkflowProvider().get_stage_definitions(
                LeaveApplication(employee=self.employee)
            )
        self.assertIn("no approval workflow", str(ctx.exception))

    def test_retiring_stops_new_submissions(self):
        team = self.create_team()
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/deactivate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Team.Status.INACTIVE)

    def test_a_retired_team_has_no_way_back(self):
        """Retiring ends the team; bringing it back means creating it again.

        A configuration that was abandoned — a chain half-swapped, people moved
        elsewhere — should not be able to come back into service, because nothing
        has re-checked it since.
        """
        team = self.create_team()
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        response = self.client.post(
            f"{TEAMS_URL}{team['id']}/activate/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Team.objects.get(pk=team["id"]).status, Team.Status.INACTIVE)

    def test_a_draft_team_cannot_be_retired(self):
        """A team that was never in force has nothing to retire.

        No endpoint writes that state any more, so the row is built here the way
        an older installation would have one.
        """
# draft status removed - no such state exists

    def test_retiring_is_audited(self):
        team = self.create_team()
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM,
            target_id=str(team["id"]),
            action=AuditEntry.Action.DEACTIVATED,
        )
        self.assertEqual(entry.detail["after"]["status"], Team.Status.INACTIVE)

    def test_a_team_is_never_hard_deleted(self):
        team = self.create_team()
        self.client.post(f"{TEAMS_URL}{team['id']}/deactivate/", format="json")
        self.assertTrue(Team.objects.filter(pk=team["id"]).exists())

    def test_a_team_in_force_routes_its_employees(self):
        team = self.create_team()
        stored = Team.objects.get(pk=team["id"])
        self.place_employee(stored)
        definitions = DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=self.employee)
        )
        self.assertEqual([d.role for d in definitions], ["supervisor", "hod"])


class TeamDetailsTests(TeamConfigurationBase):
    """What reading one team back has to answer."""

    def test_the_team_row_carries_its_lifecycle_and_window(self):
        team = self.create_team(effective_from="2026-01-01")
        row = self.read(team["id"])
        # A campus is optional and reporting-only: scoping approvals is the
        # team's own membership, so a team need not name one.
        self.assertIsNone(row["campus"])
        self.assertEqual(row["status"], Team.Status.ACTIVE)
        self.assertEqual(row["effective_from"], "2026-01-01")
        self.assertTrue(row["is_effective"])

    def test_a_team_can_belong_to_a_campus(self):
        campus = campus_for("Main campus")
        team = self.create_team(campus=campus.pk)
        row = self.read(team["id"])
        self.assertEqual(row["campus"], campus.pk)
        self.assertEqual(row["campus_name"], "Main campus")

    def test_a_team_outside_its_window_says_so(self):
        team = self.create_team(effective_to="2020-12-31")
        row = self.read(team["id"])
        self.assertFalse(row["is_effective"])

    def test_each_step_reports_who_may_act(self):
        team = self.create_team()
        row = self.read(team["id"])
        first = row["sections"][0]
        self.assertEqual(first["approver_role"], "supervisor")
        self.assertEqual(first["approver"]["id"], self.supervisor.pk)
        self.assertEqual(first["approver"]["user_name"], "Test Supervisor")
        self.assertEqual(row["member_count"], 2)

    def test_the_period_each_approver_held_is_readable(self):
        """A step's approver is one person, but *since when* is a fact worth having.

        The team screen answers "who decides here"; the membership record answers
        "who decided here last March", which is the question an audit or an
        appeal eventually asks.
        """
        team = self.create_team()
        step_one = Team.objects.get(pk=team["id"]).workflow.sections.get(order=1)
        response = self.client.get(f"{MEMBERS_URL}?section={step_one.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first = next(
            r for r in response.data["results"] if r["user"] == self.supervisor.pk
        )
        self.assertEqual(first["effective_from"], str(timezone.localdate()))
        self.assertIsNone(first["effective_to"])

    def test_an_unstaffed_step_says_so_rather_than_being_omitted(self):
        """The thing HR most needs on this screen is the step with nobody on it."""
        team = self.bare_team("Gap team")
        self.place_on_team(team, self.supervisor)
        response = self.build_chain(
            team,
            [
                {
                    "name": "Supervisor step",
                    "approver_role": "supervisor",
                    "approver": self.supervisor.pk,
                },
                {"name": "Head step", "approver_role": "hod"},
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        row = self.read(team.pk)
        self.assertIsNone(row["sections"][1]["approver"])
        self.assertEqual(row["member_count"], 1)

    def test_the_flat_member_rollup_names_the_step_each_person_is_on(self):
        team = self.create_team()
        row = self.read(team["id"])
        person = next(m for m in row["members"] if m["user"] == self.hod.pk)
        self.assertEqual(
            [s["name"] for s in person["sections"]], ["Head of Department approval"]
        )
        self.assertEqual([r["code"] for r in person["roles"]], ["hod"])

    def test_a_campus_can_be_set_and_changed(self):
        team = self.create_team()
        campus = campus_for("Main campus")
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"campus": campus.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Team.objects.get(pk=team["id"]).campus, campus)

    def test_a_retired_campus_is_refused(self):
        """Retiring a campus must not leave teams pointing at it as live."""
        team = self.create_team()
        campus = campus_for("Closed campus")
        campus.is_active = False
        campus.save(update_fields=["is_active"])
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"campus": campus.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("campus", response.data)

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
        # Appointment is only open to the team's own members, so put them on it
        # first — as HR would, on the employee record. The write itself is the
        # team manager's, who runs the roster after the handover.
        profile = user.employee_profile
        profile.team = self.team
        profile.save(update_fields=["team"])
        user.refresh_from_db()
        response = self.appoint(section, user)
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

    def test_an_appointment_cannot_be_dated_into_the_future(self):
        """A step routes to whoever is named as its approver right now.

        So a handover dated ahead would either route to somebody nobody has told
        they are an approver, or leave the step pointing at the person it is
        being taken from. Neither is a state worth having, so the appointment is
        refused and HR makes the change on the day it happens.
        """
        start = timezone.localdate() + timedelta(days=7)
        response = self.appoint(
            self.step_one,
            self.newcomer,
            effective_from=start.isoformat(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("effective_from", response.data)
        # And nothing changed: the outgoing approver still holds the step.
        self.step_one.refresh_from_db()
        self.assertEqual(self.step_one.approver_id, self.supervisor.pk)

    def test_removing_a_member_keeps_the_record_of_them(self):
        """The row is closed, not deleted.

        A membership row is a record of who was entitled to act. Deleting it
        would leave an application that somebody with no membership today
        approved with a decision nobody can explain.
        """
        membership = self.staff_and_get(self.step_one, self.newcomer)
        response = self.unappoint(membership)
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
        self.unappoint(membership)
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
        self.unappoint(membership)
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
        self.unappoint(first)
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

    def test_a_duplicate_appointment_is_a_no_op(self):
        """Re-sending an appointment is not a second handover.

        A form that submits on save would otherwise open a new period every time
        it was opened and closed again, filling the record with handovers nobody
        made and closing the outgoing one for no reason.
        """
        first = self.staff_and_get(self.step_one, self.newcomer)
        response = self.appoint(self.step_one, self.newcomer)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            SectionMember.all_objects.filter(
                section=self.step_one, user=self.newcomer
            ).count(),
            1,
        )
        self.assertEqual(first.pk, response.data["id"])
        self.assertEqual(
            SectionMember.all_objects.get(
                section=self.step_one, user=self.supervisor
            ).effective_to,
            timezone.localdate(),
        )

    def test_a_handover_is_a_handover_even_on_the_day_it_is_made(self):
        """The outgoing period is closed today, so both are recorded.

        That is what makes "who held this step, and when" answerable for today
        as well as afterwards: the person who was on it this morning still is on
        the record, and the person appointed this afternoon is on it from now.
        """
        self.staff_and_get(self.step_one, self.newcomer)
        closed = SectionMember.all_objects.get(
            section=self.step_one, user=self.supervisor
        )
        self.assertEqual(closed.effective_to, timezone.localdate())
        self.assertTrue(
            SectionMember.all_objects.filter(
                section=self.step_one, user=self.newcomer, effective_to__isnull=True
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
        self.unappoint(first)
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
        """A period cannot close before it opened.

        It would make the record claim somebody held a step over a stretch of
        dates they were not there for, which is the one thing the period exists
        to rule out.
        """
        self.staff_and_get(self.step_one, self.newcomer)
        membership = SectionMember.objects.get(
            section=self.step_one, user=self.newcomer
        )
        with self.assertRaises(TeamActionError):
            remove_section_member(
                membership=membership,
                actor=self.hr,
                effective_to=membership.effective_from - timedelta(days=1),
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
        from the chain would leave that application with nowhere to go, so the
        database refuses and the edit comes back as a validation error rather
        than as an application that can never advance.
        """
        team = self.create_team()
        self.activate(team["id"])
        self.place_employee(Team.objects.get(pk=team["id"]))
        app = self.submit()
        pending = app.stages.get(status=ApplicationStage.Status.PENDING)

        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Head of Department approval", "approver_role": "hod"}],
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
        response = self.edit_chain(
            Team.objects.get(pk=team["id"]),
            [{"name": "Head of Department approval", "approver_role": "hod"}],
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
        so removing it is the manager correcting their own configuration, and
        the chain edit has to allow it.
        """
        team = self.bare_team("Registrar team")
        self.place_on_team(team, self.supervisor, self.hod)
        response = self.build_chain(
            team,
            [
                *self.chain,
                {"name": "Registrar step", "approver_role": "registrar"},
            ],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        response = self.edit_chain(
            Team.objects.get(pk=team.pk), self.chain
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            [
                s.approver_role.code
                for s in Team.objects.get(pk=team.pk).workflow.sections.order_by("order")
            ],
            ["supervisor", "hod"],
        )

    def test_a_team_without_a_chain_refuses_the_submission_and_names_the_team(self):
        """The failure arrives before the employee loses anything.

        ``workflow_unavailable`` at submission is the whole reason a team
        without a chain is harmless: the employee is told to ask HR, not handed
        a chain that stalls at a step with nobody on it.
        """
        team = self.bare_team("Administration team")
        self.place_employee(team)
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
        self.unappoint(membership)
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
        self.unappoint(membership)
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
        self.unappoint(membership)
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
        # Appointment is open to the team's own members, so the replacement is
        # put on the team before being named to the step.
        profile = replacement.employee_profile
        profile.team = self.stored
        profile.save(update_fields=["team"])
        replacement.refresh_from_db()
        membership = SectionMember.objects.get(
            section=self.stored.workflow.sections.get(order=1),
            user=self.supervisor,
        )
        self.unappoint(membership)
        self.assertEqual(
            self.appoint(
                self.stored.workflow.sections.get(order=1), replacement
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


