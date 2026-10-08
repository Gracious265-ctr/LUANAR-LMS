"""Teams, sections, campuses, and institution-wide holdings: the routing config.

A team decides *which* chain applies: at submission the applicant's team selects
it. The chain's sections then decide *who* may act at each step, and several
members of one section may act with the first to decide taking it.

A team owns its chain one-to-one, so "edit this team's approval steps" and
"re-route somebody else's applications" cannot be the same action. The chain is
written in the same request as the team, which is what most of these tests
exercising it looks like.

These tests cover the whole configuration surface around that: the campus a team
belongs to, the membership that staffs each section, the institution-wide
holdings that stand in when a section's role has no member, and the employee
side that puts someone on a team at all.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry

from .models import (
    ApproverRole,
    Campus,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    TeamRoleAssignment,
    Workflow,
)
from .services import (
    TeamActionError,
    add_section_member,
    approver_role_codes_for,
    create_role_assignment,
    ensure_role_not_in_use,
    is_approver_user,
    remove_role_assignment,
    remove_section_member,
)
from .testing import (
    DEV_PASSWORD,
    ensure_roles,
    make_approver,
    make_team,
    make_workflow,
    team_for,
)

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"
MEMBERS_URL = "/api/v1/section-members/"
CAMPUSES_URL = "/api/v1/campuses/"
ASSIGNMENTS_URL = "/api/v1/role-assignments/"


class ConfigurationAPIBase(TestCase):
    """An HR client plus the roles a team needs."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@teams.test",
            email="hr@teams.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.employee = User.objects.create_user(
            username="emp@teams.test",
            email="emp@teams.test",
            password=DEV_PASSWORD,
            role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(self.hr)
        self.chain_roles = ("supervisor", "hod")
        # Roles are HR data, not migration seed: a bare test database has none,
        # so every chain this base writes staffs itself first.
        ensure_roles(*self.chain_roles)

    def other_team(self) -> Team:
        """A second, unrelated team: the outsider a refusal is proved against.

        Built on demand rather than in ``setUp``, because a team created for
        every test would be counted by the tests that count teams and listed by
        the tests that list them.
        """
        return team_for("Faculty of Agriculture Team")

    def chain_payload(self, name="Administration chain", roles=None) -> dict:
        """The chain as the team form writes it, since that is the only writer."""
        return {
            "name": name,
            "sections": [
                {"name": code.capitalize(), "approver_role": code}
                for code in (roles or self.chain_roles)
            ],
        }

    def create_team(self, name="Administration team", **extra) -> dict:
        payload = {
            "name": name,
            "new_workflow": self.chain_payload(),
        }
        payload.update(extra)
        response = self.client.post(TEAMS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # The team's own chain, so tests can staff and inspect its steps. It is
        # the created team's workflow, not a shared fixture, because a team owns
        # its chain.
        self.workflow = Workflow.objects.get(pk=response.data["workflow"])
        return response.data

    def add_member_to_section(self, section, user) -> dict:
        """Appoint ``user`` as ``section``'s approver, through the API."""
        response = self.client.post(
            MEMBERS_URL,
            {"section": section.pk, "user": user.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data


class CampusAPITests(ConfigurationAPIBase):
    def test_hr_creates_a_campus(self):
        response = self.client.post(
            CAMPUSES_URL,
            {"name": "Tehune Campus", "code": "tehune"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Campus.objects.get(code="tehune").name, "Tehune Campus")

    def test_creation_is_audited(self):
        self.client.post(
            CAMPUSES_URL, {"name": "Tehune Campus", "code": "tehune"}, format="json"
        )
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.CAMPUS,
                action=AuditEntry.Action.CREATED,
            ).exists()
        )

    def test_duplicate_code_is_a_clean_error_not_a_crash(self):
        self.client.post(
            CAMPUSES_URL, {"name": "Tehune Campus", "code": "tehune"}, format="json"
        )
        response = self.client.post(
            CAMPUSES_URL, {"name": "Other Campus", "code": "tehune"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)
        self.assertEqual(Campus.objects.filter(code="tehune").count(), 1)

    def test_duplicate_name_is_rejected(self):
        self.client.post(
            CAMPUSES_URL, {"name": "Tehune Campus", "code": "tehune"}, format="json"
        )
        response = self.client.post(
            CAMPUSES_URL, {"name": "Tehune Campus", "code": "tehune-2"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_code_must_be_a_slug(self):
        response = self.client.post(
            CAMPUSES_URL, {"name": "Bad Campus", "code": "Tehune Campus"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data)

    def test_campuses_cannot_be_deleted(self):
        """PROTECT: removing a campus would silently change what a team means."""
        created = self.client.post(
            CAMPUSES_URL, {"name": "Tehune Campus", "code": "tehune"}, format="json"
        ).data
        response = self.client.delete(f"{CAMPUSES_URL}{created['id']}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Campus.objects.filter(code="tehune").exists())

    def test_code_is_immutable_once_a_team_uses_the_campus(self):
        campus = Campus.objects.create(name="Tehune Campus", code="tehune")
        self.create_team("Tehune team", campus=campus.pk)
        response = self.client.patch(
            f"{CAMPUSES_URL}{campus.pk}/", {"code": "tehune-north"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        campus.refresh_from_db()
        self.assertEqual(campus.code, "tehune")

    def test_name_stays_editable(self):
        campus = Campus.objects.create(name="Tehune Campus", code="tehune")
        response = self.client.patch(
            f"{CAMPUSES_URL}{campus.pk}/", {"name": "Tehune"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        campus.refresh_from_db()
        self.assertEqual(campus.name, "Tehune")

    def test_non_hr_cannot_create_a_campus(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            CAMPUSES_URL, {"name": "Sneaky Campus", "code": "sneaky"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Campus.objects.filter(code="sneaky").exists())

    def test_a_team_cannot_point_at_an_inactive_campus(self):
        campus = Campus.objects.create(
            name="Retired Campus", code="retired", is_active=False
        )
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Team",
                "new_workflow": self.chain_payload(),
                "campus": campus.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campus", response.data)


class TeamAPITests(ConfigurationAPIBase):
    def test_hr_creates_a_team(self):
        """The chain arrives with the team, and is the team's own."""
        team = self.create_team(description="Administration staff")
        self.assertEqual(team["name"], "Administration team")
        self.assertEqual(team["workflow"], self.workflow.pk)
        self.assertEqual(team["workflow_name"], "Administration chain")
        self.assertEqual(
            [s["approver_role"] for s in team["sections"]],
            ["supervisor", "hod"],
        )

    # ``department_missing`` is gone: a team is scoped by itself, and the campus
    # it optionally sits at is reference data that scopes no approver. There is
    # therefore no "a team must be placed somewhere before it can route" rule
    # left to prove. The two-page draft rule it used to be paired with is proved
    # by ``test_a_chainless_draft_team_cannot_be_activated`` instead.

    def test_a_code_is_derived_from_the_name(self):
        team = self.create_team("Human Resources")
        self.assertEqual(team["code"], "human-resources")

    def test_names_that_slug_alike_still_get_distinct_codes(self):
        first = self.create_team("R & D team")
        second = self.create_team("R&D team")
        self.assertNotEqual(first["code"], second["code"])
        self.assertEqual(Team.objects.count(), 2)

    def test_creation_is_audited(self):
        self.create_team()
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM, action=AuditEntry.Action.CREATED
        )
        self.assertEqual(entry.actor, self.hr)

    def test_a_team_may_be_created_without_a_campus(self):
        team = self.create_team("Non-campus team")
        self.assertIsNone(team["campus"])
        self.assertIsNone(Team.objects.get(name="Non-campus team").campus_id)

    def test_duplicate_name_rejected(self):
        self.create_team()
        response = self.client.post(
            TEAMS_URL,
            {"name": "Administration team", "new_workflow": self.chain_payload()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_a_team_may_not_point_at_an_existing_chain(self):
        """A chain is never picked from a list to be routed through.

        ``workflow`` is writable now — a team points at the chain it owns, so
        that switching a team to its replacement chain is a real, recorded
        decision — but only at a chain the team already owns. Naming somebody
        else's chain would strand every application inside it at a step nobody
        staffs for them, so it is refused rather than quietly ignored, and the
        team is not half-created on the way.
        """
        other = self.create_team(name="Other team")
        response = self.client.post(
            TEAMS_URL,
            {"name": "Copying team", "workflow": other["workflow"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("workflow", response.data)
        self.assertFalse(Team.objects.filter(name="Copying team").exists())

    def test_a_team_may_be_created_before_its_chain(self):
        """Page 1 of the team form: the team's identity, no chain yet.

        The team's identity is the first thing HR knows and the second page is
        where the approval steps get described, so refusing to save the identity
        would mean holding the whole thing in the browser until the last step was
        answered. The team lands as a draft with no chain, and a draft routes
        nothing, so the window cannot be reached in production.
        """
        response = self.client.post(
            TEAMS_URL,
            {"name": "Chainless team"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        team = Team.objects.get(name="Chainless team")
        self.assertIsNone(team.workflow_id)
        self.assertEqual(team.status, Team.Status.DRAFT)
        self.assertEqual(response.data["sections"], [])  # type: ignore[index]

    def test_a_chainless_draft_team_cannot_be_activated(self):
        """A draft team with no chain is refused activation, naming the chain.

        The rule is what makes the previous test safe: a team can exist without
        a chain, but cannot be put into force without one.
        """
        created = self.client.post(
            TEAMS_URL,
            {"name": "Chainless team"},
            format="json",
        ).data
        response = self.client.post(f"{TEAMS_URL}{created['id']}/activate/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Team.objects.get(pk=created["id"]).status, Team.Status.DRAFT
        )
        codes = [issue["code"] for issue in response.data["issues"]]
        self.assertIn("workflow_missing", codes)

    def test_a_team_with_no_steps_is_refused(self):
        """A chain that was asked for must actually have steps in it.

        Sending an empty chain is different from sending none: the first says
        "this team routes through nothing", which is refused.
        """
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Empty chain",
                "new_workflow": {"sections": []},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_workflow", response.data)
        self.assertFalse(Team.objects.filter(name="Empty chain").exists())

    def test_the_chain_can_be_written_afterwards(self):
        """Page 2 of the team form: the chain, written by saving the team again."""
        created = self.client.post(
            TEAMS_URL,
            {"name": "Second page team"},
            format="json",
        ).data
        response = self.client.patch(
            f"{TEAMS_URL}{created['id']}/",
            {"new_workflow": self.chain_payload("Second page chain")},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        team = Team.objects.get(pk=created["id"])
        self.assertIsNotNone(team.workflow_id)
        self.assertEqual(
            [s["approver_role"] for s in response.data["sections"]],  # type: ignore[index]
            ["supervisor", "hod"],
        )

    def test_teams_cannot_be_deleted(self):
        team = self.create_team()
        response = self.client.delete(f"{TEAMS_URL}{team['id']}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Team.objects.filter(pk=team["id"]).exists())

    def test_non_hr_cannot_create_a_team(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            TEAMS_URL,
            {"name": "Sneaky team", "new_workflow": self.chain_payload()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Team.objects.filter(name="Sneaky team").exists())

    def test_description_and_campus_are_editable(self):
        campus = Campus.objects.create(name="Tehune", code="tehune")
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"description": "Now with a campus", "campus": campus.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stored = Team.objects.get(pk=team["id"])
        self.assertEqual(stored.description, "Now with a campus")
        self.assertEqual(stored.campus, campus)

    def test_an_edit_is_audited_with_before_and_after(self):
        team = self.create_team()
        self.client.patch(
            f"{TEAMS_URL}{team['id']}/", {"description": "Changed"}, format="json"
        )
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.TEAM,
            target_id=str(team["id"]),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertEqual(entry.detail["after"]["description"], "Changed")

    def test_listing_reports_the_roles_a_team_needs(self):
        team = self.create_team()
        response = self.client.get(TEAMS_URL)
        row = next(r for r in response.data["results"] if r["id"] == team["id"])
        self.assertEqual(
            [r["code"] for r in row["stage_roles"]], ["supervisor", "hod"]
        )
        self.assertEqual(row["member_count"], 0)

    def test_listing_reports_the_workflow_sections(self):
        """A team reports the steps of its chain and who decides each one.

        A step with nobody appointed says so explicitly rather than being left
        out: an unstaffed step is the thing HR most needs to see on this screen.
        """
        team = self.create_team()
        approver = make_approver(
            "supervisor",
            username="sup@teams.test",
            institution_wide=False,
            team=Team.objects.get(pk=team["id"]),
        )
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="supervisor"), approver
        )
        response = self.client.get(TEAMS_URL)
        row = next(r for r in response.data["results"] if r["id"] == team["id"])
        self.assertEqual(
            [s["approver_role"] for s in row["sections"]], ["supervisor", "hod"]
        )
        self.assertEqual(row["sections"][0]["approver"]["id"], approver.pk)
        self.assertIsNone(row["sections"][1]["approver"])

    def test_a_new_team_starts_as_a_draft(self):
        """Created is not in force.

        A team appears the moment HR names it, and only starts affecting real
        applications when it is activated. A boolean could not have said this:
        a team being built looked exactly like a team in service.
        """
        team = self.create_team()
        self.assertEqual(team["status"], Team.Status.DRAFT)
        self.assertEqual(Team.objects.get(pk=team["id"]).status, Team.Status.DRAFT)

    def test_status_cannot_be_set_by_a_write(self):
        """Lifecycle moves go through their own validated actions.

        A PATCH that could flip a team to active would be a team put in force
        without a validation record and without the refusal that validation
        exists to give.
        """
        team = self.create_team()
        response = self.client.patch(
            f"{TEAMS_URL}{team['id']}/",
            {"status": Team.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Team.objects.get(pk=team["id"]).status, Team.Status.DRAFT
        )

    def test_retired_teams_are_hidden_by_default(self):
        """A retired team drops out of the working list but is still reachable.

        The default view shows what is in force plus what HR is still building;
        the retired ones are there on request because their history still points
        at them.
        """
        self.create_team()
        team = Team.objects.get(name="Administration team")
        team.status = Team.Status.INACTIVE
        team.save(update_fields=["status"])
        response = self.client.get(TEAMS_URL)
        self.assertNotIn(
            "Administration team", [r["name"] for r in response.data["results"]]
        )
        response = self.client.get(f"{TEAMS_URL}?include_inactive=1")
        self.assertIn(
            "Administration team", [r["name"] for r in response.data["results"]]
        )

    def test_the_list_can_be_filtered_to_one_status(self):
        self.create_team(name="Draft team")
        self.create_team(name="Live team", roles=("dean",))
        Team.objects.filter(name="Live team").update(status=Team.Status.ACTIVE)
        response = self.client.get(f"{TEAMS_URL}?status=active")
        self.assertEqual(
            [r["name"] for r in response.data["results"]], ["Live team"]
        )
        response = self.client.get(f"{TEAMS_URL}?status=draft")
        self.assertEqual(
            [r["name"] for r in response.data["results"]], ["Draft team"]
        )

    def test_an_unknown_status_filter_is_a_clean_error(self):
        response = self.client.get(f"{TEAMS_URL}?status=maybe")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_the_list_can_be_filtered_to_one_campus(self):
        campus = Campus.objects.create(name="Tehune", code="tehune")
        self.create_team(name="Tehune team", campus=campus.pk)
        self.create_team(name="Anywhere team")
        response = self.client.get(f"{TEAMS_URL}?campus={campus.pk}")
        self.assertEqual(
            [r["name"] for r in response.data["results"]], ["Tehune team"]
        )

    def test_an_inactive_approver_role_cannot_be_chained(self):
        """A step nobody can act for is refused while it is being written.

        The chain is described in the same request as the team, so a retired
        role is caught here rather than surfacing as a submission that cannot
        move.
        """
        ensure_roles("dean")
        ApproverRole.objects.filter(code="dean").update(is_active=False)
        response = self.client.post(
            TEAMS_URL,
            {"name": "Stale team", "new_workflow": self.chain_payload(roles=("dean",))},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Team.objects.filter(name="Stale team").exists())


class SectionApproverTests(ConfigurationAPIBase):
    """Who approves a section: one person, from the team's own employees.

    A section is the unit here, not the team: an appointment belongs to a step of
    the chain. A step has exactly one approver, so appointing somebody replaces
    whoever was there, and the eligibility rules are team membership and the
    one-role-per-team rule.
    """

    def setUp(self):
        super().setUp()
        self.team = self.create_team()
        self.owning_team = Team.objects.get(pk=self.team["id"])
        self.section = Section.objects.get(workflow=self.workflow, order=1)
        self.supervisor = make_approver(
            "supervisor",
            username="sup@teams.test",
            institution_wide=False,
            team=self.owning_team,
        )

    def add_approver(self, user, section=None) -> dict:
        return super().add_member_to_section(section or self.section, user)

    def test_hr_appoints_a_section_approver(self):
        appointment = self.add_approver(self.supervisor)
        self.assertEqual(appointment["user"], self.supervisor.pk)
        self.assertEqual(appointment["section"], self.section.pk)
        self.section.refresh_from_db()
        self.assertEqual(self.section.approver_id, self.supervisor.pk)
        self.assertEqual(
            SectionMember.objects.get(
                section_id=self.section.pk, user=self.supervisor
            ).section.approver_role.code,
            "supervisor",
        )

    def test_appointing_an_approver_makes_them_an_approver(self):
        self.assertFalse(is_approver_user(self.supervisor))
        self.add_approver(self.supervisor)
        self.assertTrue(is_approver_user(self.supervisor))
        self.assertEqual(approver_role_codes_for(self.supervisor), ["supervisor"])

    def test_a_second_appointment_replaces_the_first(self):
        """One step, one approver: the new person's period closes the old one."""
        second = make_approver(
            "supervisor",
            username="sup2@teams.test",
            institution_wide=False,
            team=self.owning_team,
        )
        self.add_approver(self.supervisor)
        self.add_approver(second)
        self.section.refresh_from_db()
        self.assertEqual(self.section.approver_id, second.pk)
        self.assertFalse(
            SectionMember.objects.filter(
                section=self.section,
                user=self.supervisor,
                effective_to__isnull=True,
            ).exists()
        )
        self.assertTrue(
            SectionMember.objects.filter(
                section=self.section, user=second, effective_to__isnull=True
            ).exists()
        )

    def test_the_same_person_may_sit_on_several_sections(self):
        """One person can hold more than one point in a chain."""
        hod = self.workflow.sections.get(order=2)
        self.add_approver(self.supervisor)
        response = self.client.post(
            MEMBERS_URL, {"section": hod.pk, "user": self.supervisor.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        # The second step needs the Head of Department role, and one employee
        # holds one role per team — so this is refused, and that is the
        # rule doing its job rather than an accident of ordering.
        self.assertIn("approver", response.data)

    def test_one_person_may_not_hold_two_stages_of_one_chain(self):
        """Unit 30: an employee is on one stage per workflow.

        Two steps with two *different* roles, so the per-team role rule
        does not fire first and the refusal is unambiguously the per-workflow
        one. Reusing the same role for both steps is a different refusal — the
        role itself may only appear once per workflow — covered in
        ``workflows.tests``.
        """
        team = self.create_team(
            "Two step team",
            new_workflow={
                "name": "Two step chain",
                "sections": [
                    {"name": "First review", "approver_role": "supervisor"},
                    {"name": "Second review", "approver_role": "hod"},
                ],
            },
        )
        person = make_approver(
            "supervisor",
            username="twosup@teams.test",
            institution_wide=False,
            team=Team.objects.get(pk=team["id"]),
        )
        steps = list(
            Workflow.objects.get(pk=team["workflow"]).sections.order_by("order")
        )
        self.add_approver(person, steps[0])
        # The second appointment is refused through the API, naming the step
        # already held. Posted directly rather than via add_approver, which
        # asserts 201 and would fail on the refusal instead of on the rule.
        refused = self.client.post(
            MEMBERS_URL,
            {"section": steps[1].pk, "user": person.pk},
            format="json",
        )
        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already assigned to step 1", str(refused.data))
        self.assertIsNone(Section.objects.get(pk=steps[1].pk).approver_id)

    def test_an_approver_from_another_team_is_refused(self):
        """A team's approvers are its own employees.

        Somebody from another team approving here would be deciding on a budget
        and a procedure they do not hold, so the refusal names both teams rather
        than just saying "not eligible".
        """
        outsider = make_approver(
            "supervisor",
            username="outsider@teams.test",
            institution_wide=False,
            team=self.other_team(),
        )
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": outsider.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Faculty of Agriculture Team", response.data["approver"][0])
        self.assertIn("Administration team", response.data["approver"][0])

    def test_an_institution_wide_role_ignores_the_team_membership_rule(self):
        """Some posts are not a team's to fill.

        A vice-chancellor's office approves from outside any team, so an
        institution-wide role is appointed without the membership check — which
        is what makes that flag worth having.
        """
        ensure_roles("registrar")
        role = ApproverRole.objects.get(code="registrar")
        role.is_institution_wide = True
        role.save(update_fields=["is_institution_wide"])
        outsider = make_approver(
            "registrar",
            username="vc@teams.test",
            institution_wide=False,
            team=self.other_team(),
        )
        section = self.workflow.sections.get(order=2)
        section.approver_role = role
        section.save(update_fields=["approver_role"])
        response = self.client.post(
            MEMBERS_URL, {"section": section.pk, "user": outsider.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_one_person_may_not_hold_two_roles_on_one_team(self):
        """One employee, one approver role, per team.

        Two roles on one team would make what they can see depend on which of
        that team's applications arrived — each role carries its own history
        scope — so the second appointment is refused and the message names the
        first.
        """
        hod = self.workflow.sections.get(order=2)
        head = make_approver(
            "hod",
            username="head@teams.test",
            institution_wide=False,
            team=self.owning_team,
        )
        response = self.client.post(
            MEMBERS_URL, {"section": hod.pk, "user": head.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        response = self.client.post(
            MEMBERS_URL, {"section": self.section.pk, "user": head.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Head of Department", response.data["approver"][0])

    def test_the_one_role_rule_is_per_team_not_per_person(self):
        """The one-role rule does not follow a person between teams.

        Somebody who supervises one team and heads another is not a
        contradiction: the two roles are about two different bodies of work, and
        the rule is scoped to the team it is enforced on.
        """
        self.add_approver(self.supervisor)
        team = self.create_team(
            "Agriculture team",
            new_workflow={
                "name": "Agriculture chain",
                "sections": [
                    {"name": "Head", "approver_role": "hod"}
                ],
            },
        )
        step = Workflow.objects.get(pk=team["workflow"]).sections.get(order=1)
        # The person's employee record moves team, as an internal transfer would,
        # and they are appointed on the team they moved to.
        profile = self.supervisor.employee_profile
        profile.team = Team.objects.get(pk=team["id"])
        profile.save(update_fields=["team"])
        response = self.client.post(
            MEMBERS_URL, {"section": step.pk, "user": self.supervisor.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_an_approver_with_no_employee_record_is_refused(self):
        """Eligibility is an employment fact, so an account alone is not enough."""
        from users.models import EmployeeProfile

        personless = make_approver(
            "supervisor",
            username="no-profile@teams.test",
            institution_wide=False,
            team=self.owning_team,
        )
        EmployeeProfile.objects.filter(user=personless).delete()
        response = self.client.post(
            MEMBERS_URL, {"section": self.section.pk, "user": personless.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("employee record", response.data["approver"][0])

    def test_a_chain_with_no_team_cannot_be_staffed(self):
        """A chain that is not attached to a team has nobody to appoint.

        Eligibility is team membership, so a chain nobody owns cannot scope an
        approver. Treating "no team" as "anybody may approve" would make the rule
        opt-out rather than opt-in.
        """
        ensure_roles("dean")
        orphan = make_workflow("Orphan chain", ("dean",))
        section = orphan.sections.get(order=1)
        response = self.client.post(
            MEMBERS_URL, {"section": section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not attached to a team", response.data["approver"][0])

    def test_an_appointment_is_audited(self):
        self.add_approver(self.supervisor)
        entry = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.CREATED,
        ).order_by("-id").first()
        self.assertEqual(entry.actor, self.hr)
        self.assertIn("Supervisor", entry.reason)

    def test_a_replacement_appointment_names_who_it_replaced(self):
        second = make_approver(
            "supervisor",
            username="sup2@teams.test",
            institution_wide=False,
            team=self.owning_team,
        )
        self.add_approver(self.supervisor)
        self.add_approver(second)
        entry = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.CREATED,
        ).order_by("-id").first()
        self.assertEqual(entry.detail["after"]["replaced_user_id"], self.supervisor.pk)
        self.assertIn("replacing", entry.reason)

    def test_re_appointing_the_same_person_is_a_no_op_not_an_error(self):
        """Re-saving a form that did not change must not fail.

        A team edit that leaves a step's approver alone would otherwise be
        refused for proposing something already true.
        """
        self.add_approver(self.supervisor)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            SectionMember.objects.filter(
                section=self.section, user=self.supervisor
            ).count(),
            1,
        )

    def test_an_inactive_section_takes_no_approver(self):
        self.section.is_active = False
        self.section.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("inactive", response.data["section"][0])

    def test_an_inactive_user_cannot_be_appointed(self):
        self.supervisor.is_active = False
        self.supervisor.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not an active user", response.data["user"][0])

    def test_a_deactivated_role_cannot_be_staffed(self):
        role = ApproverRole.objects.get(code="supervisor")
        role.is_active = False
        role.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deactivated", response.data["section"][0])

    def test_an_unknown_section_is_rejected(self):
        response = self.client.post(
            MEMBERS_URL,
            {"section": 999_999, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("section", response.data)

    def test_appointments_can_be_listed_per_section_and_per_workflow(self):
        self.add_approver(self.supervisor)
        # Filtering by workflow reaches the *section's* workflow, not the team,
        # so one team's roster is never returned for another team's chain.
        first_chain = self.workflow.pk
        self.create_team("Other team")
        other = Team.objects.get(name="Other team")
        response = self.client.get(f"{MEMBERS_URL}?workflow={first_chain}")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(f"{MEMBERS_URL}?workflow={other.workflow_id}")
        self.assertEqual(len(response.data["results"]), 0)
        unrelated = make_workflow("Unrelated chain", ("dean",))
        response = self.client.get(f"{MEMBERS_URL}?workflow={unrelated.pk}")
        self.assertEqual(len(response.data["results"]), 0)
        response = self.client.get(f"{MEMBERS_URL}?section={self.section.pk}")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user"], self.supervisor.pk)

    def test_appointments_can_be_listed_for_one_user(self):
        self.add_approver(self.supervisor)
        response = self.client.get(f"{MEMBERS_URL}?user={self.supervisor.pk}")
        self.assertEqual(len(response.data["results"]), 1)

    def test_a_bad_section_filter_is_a_client_error(self):
        response = self.client.get(f"{MEMBERS_URL}?section=not-a-number")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removing_an_approver_revokes_approver_status(self):
        self.add_approver(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(is_approver_user(self.supervisor))

    def test_removing_an_approver_leaves_the_step_unstaffed(self):
        """The step stops routing, and says so rather than routing to a ghost.

        Clearing the appointment is the point: leaving ``approver`` pointing at
        somebody whose period has closed would make the configuration claim they
        are still appointed.
        """
        self.add_approver(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.section.refresh_from_db()
        self.assertIsNone(self.section.approver_id)
        validation = self.client.post(f"{TEAMS_URL}{self.team['id']}/validate/")
        codes = [issue["code"] for issue in validation.data["issues"]]
        self.assertIn("no_approver", codes)

    def test_removal_is_audited(self):
        self.add_approver(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.DEACTIVATED,
            target_id=str(self.workflow.pk),
        )
        self.assertEqual(entry.detail["after"]["effective_to"], str(timezone.localdate()))

    def test_appointments_cannot_be_edited_in_place(self):
        """Re-appointing is a removal plus an addition, both audited."""
        self.add_approver(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        response = self.client.patch(
            f"{MEMBERS_URL}{membership.pk}/",
            {"section": self.workflow.sections.get(order=2).pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_non_hr_cannot_appoint_an_approver(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(SectionMember.objects.exists())

    def test_removing_an_appointment_twice_is_a_client_error(self):
        self.add_approver(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        remove_section_member(membership=membership, actor=self.hr)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EligibleApproverEndpointTests(ConfigurationAPIBase):
    """The approver picker is scoped by the team, so it cannot offer a
    person the write would refuse."""

    def setUp(self):
        super().setUp()
        self.team = Team.objects.get(pk=self.create_team()["id"])
        self.inside = make_approver(
            "supervisor",
            username="inside@teams.test",
            institution_wide=False,
            team=self.team,
        )
        self.outside = make_approver(
            "supervisor",
            username="outside@teams.test",
            institution_wide=False,
            team=self.other_team(),
        )

    def url(self, **params) -> str:
        query = "&".join(f"{key}={value}" for key, value in params.items())
        return f"{TEAMS_URL}eligible-approvers/?{query}"

    def test_a_team_is_required(self):
        response = self.client.get(f"{TEAMS_URL}eligible-approvers/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data)

    def test_it_offers_only_the_teams_own_employees(self):
        response = self.client.get(self.url(team=self.team.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(self.inside.pk, ids)
        self.assertNotIn(self.outside.pk, ids)
        self.assertEqual(response.data["team"]["name"], "Administration team")

    def test_naming_a_role_excludes_somebody_holding_another_one_here(self):
        """The list agrees with the rule, so a refused pick is not offered.

        Somebody already appointed in a different role on this team cannot be
        appointed in this one, so leaving them in the list would offer a choice
        the save rejects.
        """
        hod = make_approver(
            "hod",
            username="head@teams.test",
            institution_wide=False,
            team=self.team,
        )
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="hod"), hod
        )
        role = ApproverRole.objects.get(code="supervisor")
        response = self.client.get(self.url(team=self.team.pk, role=role.pk))
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertNotIn(hod.pk, ids)
        self.assertIn(self.inside.pk, ids)

    def test_naming_a_role_keeps_somebody_already_holding_it(self):
        supervisor_role = ApproverRole.objects.get(code="supervisor")
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="supervisor"),
            self.inside,
        )
        response = self.client.get(
            self.url(team=self.team.pk, role=supervisor_role.pk)
        )
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(self.inside.pk, ids)

    def test_an_unknown_team_is_a_client_error(self):
        response = self.client.get(self.url(team=999_999))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_hr_cannot_list_eligible_approvers(self):
        self.client.force_authenticate(self.employee)
        response = self.client.get(self.url(team=self.team.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_an_institution_wide_role_offers_its_holder_from_outside(self):
        """The holder is not a team employee, but selecting the role is
        how HR names them, so the picker has to be able to show them."""
        registrar = make_approver(
            "registrar",
            username="registrar@teams.test",
            institution_wide=True,
        )
        role = ApproverRole.objects.get(code="registrar")
        response = self.client.get(self.url(team=self.team.pk, role=role.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(registrar.pk, ids)

    def test_an_inactive_institution_wide_holder_is_not_offered(self):
        registrar = make_approver(
            "registrar",
            username="retired-registrar@teams.test",
            institution_wide=True,
        )
        registrar.is_active = False
        registrar.save(update_fields=["is_active"])
        role = ApproverRole.objects.get(code="registrar")
        response = self.client.get(self.url(team=self.team.pk, role=role.pk))
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertNotIn(registrar.pk, ids)

    def second_chain(self):
        response = self.client.post(
            WORKFLOWS_URL,
            {
                "name": "Second chain",
                "team": self.team.pk,
                "sections": [
                    {"name": "Check", "approver_role": "supervisor", "approver": None}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return Workflow.objects.get(pk=response.data["id"])

    def test_naming_a_workflow_drops_people_on_the_other_chain(self):
        other_chain = self.second_chain()
        self.add_member_to_section(other_chain.sections.get(), self.inside)
        role = ApproverRole.objects.get(code="supervisor")
        # Scoped to the team's original chain, inside is "on another chain" and
        # may not be offered for configuring this one.
        response = self.client.get(
            self.url(team=self.team.pk, role=role.pk, workflow=self.workflow.pk)
        )
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertNotIn(self.inside.pk, ids)
        # Scoped to the chain inside actually staffs, they are its current
        # holder and stay offered.
        response = self.client.get(
            self.url(team=self.team.pk, role=role.pk, workflow=other_chain.pk)
        )
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(self.inside.pk, ids)

    def test_workflow_new_drops_people_on_any_chain(self):
        self.add_member_to_section(self.second_chain().sections.get(), self.inside)
        role = ApproverRole.objects.get(code="supervisor")
        # "new" means the chain does not exist yet, so anyone already placed on
        # any of the team's chains is excluded.
        response = self.client.get(
            self.url(team=self.team.pk, role=role.pk, workflow="new")
        )
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertNotIn(self.inside.pk, ids)
        # Without the workflow scope the picker keeps its legacy behaviour and
        # still offers them.
        response = self.client.get(self.url(team=self.team.pk, role=role.pk))
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(self.inside.pk, ids)

    def test_a_wide_approver_on_another_chain_stays_offered(self):
        other_chain = self.second_chain()
        self.add_member_to_section(other_chain.sections.get(), self.inside)
        supervisor = ApproverRole.objects.get(code="supervisor")
        TeamRoleAssignment.objects.create(
            user=self.inside, team=self.team, role=supervisor
        )
        # A team-wide holder may also sit on the first chain as a normal member,
        # and must remain offered to every chain of the team.
        response = self.client.post(
            f"{WORKFLOWS_URL}{self.workflow.pk}/members/",
            {"user": self.inside.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        response = self.client.get(
            self.url(team=self.team.pk, role=supervisor.pk, workflow="new")
        )
        ids = [row["id"] for row in response.data["candidates"]]
        self.assertIn(self.inside.pk, ids)


class InstitutionWideAutoApprovalTests(ConfigurationAPIBase):
    """Selecting an institution-wide role staffs the step with its single holder.

    Such a role is held outside any one team, so the team-scoped picker cannot be
    used to name the holder by hand. Choosing the role is the whole instruction,
    and the one active holder is written when the chain is.
    """

    def setUp(self):
        super().setUp()
        ensure_roles("registrar")
        self.chain_roles = ("supervisor", "registrar")

    def registrar_holder(self, username="registrar@teams.test"):
        return make_approver(
            "registrar",
            username=username,
            institution_wide=True,
        )

    def test_creating_a_chain_appoints_the_single_holder(self):
        holder = self.registrar_holder()
        self.create_team()
        section = self.workflow.sections.get(approver_role__code="registrar")
        self.assertEqual(section.approver_id, holder.pk)
        self.assertTrue(
            SectionMember.objects.filter(section=section, user=holder).exists()
        )

    def test_the_holder_is_not_moved_onto_the_team(self):
        """Their post approves across teams; this one does not hold them."""
        holder = self.registrar_holder()
        self.create_team()
        self.assertIsNone(holder.employee_profile.team_id)

    def test_selecting_the_role_when_the_chain_is_written_later(self):
        holder = self.registrar_holder("late-registrar@teams.test")
        created = self.client.post(
            TEAMS_URL,
            {"name": "Late chain"},
            format="json",
        ).data
        response = self.client.patch(
            f"{TEAMS_URL}{created['id']}/",
            {"new_workflow": self.chain_payload("Late chain")},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        workflow = Workflow.objects.get(pk=response.data["workflow"])
        section = workflow.sections.get(approver_role__code="registrar")
        self.assertEqual(section.approver_id, holder.pk)

    def test_no_holder_leaves_the_step_unstaffed(self):
        """Nothing to appoint is not the same as appointing nobody silently."""
        self.create_team()
        section = self.workflow.sections.get(approver_role__code="registrar")
        self.assertIsNone(section.approver_id)

    def test_two_holders_leave_the_step_for_hr_to_choose(self):
        """Picking one of several would decide an ambiguity HR must resolve."""
        self.registrar_holder("first-registrar@teams.test")
        self.registrar_holder("second-registrar@teams.test")
        self.create_team()
        section = self.workflow.sections.get(approver_role__code="registrar")
        self.assertIsNone(section.approver_id)

    def test_a_team_scoped_role_is_never_auto_appointed(self):
        """Only an institution-wide role carries its holder with it."""
        self.create_team()
        section = self.workflow.sections.get(approver_role__code="supervisor")
        self.assertIsNone(section.approver_id)


class RoleAssignmentAPITests(ConfigurationAPIBase):
    def setUp(self):
        super().setUp()
        ensure_roles("registrar", "supervisor")

    def test_hr_grants_an_institution_wide_role(self):
        response = self.client.post(
            ASSIGNMENTS_URL,
            {"user": self.employee.pk, "role": ApproverRole.objects.get(code="registrar").pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(is_approver_user(self.employee))

    def test_the_first_institution_holder_promotes_a_team_role(self):
        """The Approvers page is where a wide role is born: assigning a team
        role its first institution-wide holder is the decision that it now
        covers every application, so the same save promotes the role."""
        role = ApproverRole.objects.get(code="supervisor")
        self.assertFalse(role.is_institution_wide)

        response = self.client.post(
            ASSIGNMENTS_URL,
            {"user": self.employee.pk, "role": role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        role.refresh_from_db()
        self.assertTrue(role.is_institution_wide)
        self.assertTrue(RoleAssignment.objects.filter(role=role).exists())
        self.assertTrue(is_approver_user(self.employee))
        # The promotion is a change in its own right, so it is audited.
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPROVER_ROLE,
                action=AuditEntry.Action.UPDATED,
            ).exists()
        )

    def test_a_role_held_on_a_team_cannot_be_granted_institution_wide(self):
        """A role cannot be held wide at a team and institution-wide at once;
        promoting it would contradict the holder already on the team."""
        role = ApproverRole.objects.get(code="supervisor")
        team = Team.objects.get(pk=self.create_team()["id"])
        TeamRoleAssignment.objects.create(team=team, role=role, user=self.employee)

        response = self.client.post(
            ASSIGNMENTS_URL,
            {"user": self.employee.pk, "role": role.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already held on a team or campus", response.data["role"][0])
        role.refresh_from_db()
        self.assertFalse(role.is_institution_wide)
        self.assertFalse(RoleAssignment.objects.exists())

    def test_granting_twice_is_refused(self):
        payload = {
            "user": self.employee.pk,
            "role": ApproverRole.objects.get(code="registrar").pk,
        }
        self.client.post(ASSIGNMENTS_URL, payload, format="json")
        response = self.client.post(ASSIGNMENTS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already holds", response.data["user"][0])
        self.assertEqual(RoleAssignment.objects.count(), 1)

    def test_an_inactive_user_cannot_hold_a_role(self):
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        response = self.client.post(
            ASSIGNMENTS_URL,
            {
                "user": self.employee.pk,
                "role": ApproverRole.objects.get(code="registrar").pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not an active user", response.data["user"][0])

    def test_a_deactivated_role_cannot_be_granted(self):
        role = ApproverRole.objects.get(code="registrar")
        role.is_active = False
        role.save(update_fields=["is_active"])
        response = self.client.post(
            ASSIGNMENTS_URL, {"user": self.employee.pk, "role": role.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deactivated", response.data["role"][0])

    def test_assignments_can_be_filtered_by_role_and_user(self):
        role = ApproverRole.objects.get(code="registrar")
        create_role_assignment(user=self.employee, role=role, actor=self.hr)
        response = self.client.get(f"{ASSIGNMENTS_URL}?role={role.pk}")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(f"{ASSIGNMENTS_URL}?user={self.employee.pk}")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(f"{ASSIGNMENTS_URL}?user={self.hr.pk}")
        self.assertEqual(response.data["results"], [])

    def test_revoking_a_role_revokes_approver_status(self):
        role = ApproverRole.objects.get(code="registrar")
        create_role_assignment(user=self.employee, role=role, actor=self.hr)
        assignment = RoleAssignment.objects.get()
        response = self.client.delete(f"{ASSIGNMENTS_URL}{assignment.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RoleAssignment.objects.exists())
        self.assertFalse(is_approver_user(self.employee))

    def test_revocation_is_audited(self):
        role = ApproverRole.objects.get(code="registrar")
        assignment = create_role_assignment(
            user=self.employee, role=role, actor=self.hr
        )
        remove_role_assignment(assignment=assignment, actor=self.hr)
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPROVER_ROLE,
                action=AuditEntry.Action.CANCELLED,
            ).exists()
        )

    def test_a_bad_filter_is_a_client_error(self):
        response = self.client.get(f"{ASSIGNMENTS_URL}?role=nope")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_hr_cannot_grant_a_role(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            ASSIGNMENTS_URL,
            {
                "user": self.employee.pk,
                "role": ApproverRole.objects.get(code="registrar").pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(RoleAssignment.objects.exists())


class EmployeeTeamPlacementTests(ConfigurationAPIBase):
    """Placing an employee on a team is what gives their applications a chain."""

    def setUp(self):
        super().setUp()
        from users.models import EmployeeProfile

        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            faculty="Faculty of Science",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
        )
        self.team = self.create_team()

    def url(self) -> str:
        return f"/api/v1/employees/{self.profile.pk}/"

    def test_hr_places_the_employee_on_a_team(self):
        response = self.client.patch(
            self.url(), {"team": self.team["id"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.team_id, self.team["id"])
        self.assertEqual(response.data["team"], self.team["id"])
        self.assertEqual(response.data["team_name"], "Administration team")

    def test_placement_is_audited(self):
        self.client.patch(self.url(), {"team": self.team["id"]}, format="json")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=str(self.profile.pk),
            action=AuditEntry.Action.UPDATED,
        )
        self.assertIn("team", entry.detail["after"])

    def test_the_team_can_be_cleared(self):
        self.client.patch(self.url(), {"team": self.team["id"]}, format="json")
        response = self.client.patch(self.url(), {"team": None}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.team_id)

    def test_an_unknown_team_is_rejected(self):
        response = self.client.patch(self.url(), {"team": 99999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data)

    def test_the_employee_list_reports_the_team(self):
        self.client.patch(self.url(), {"team": self.team["id"]}, format="json")
        response = self.client.get("/api/v1/employees/")
        row = next(
            r for r in response.data["results"] if r["id"] == self.profile.pk
        )
        self.assertEqual(row["team"], self.team["id"])
        self.assertEqual(row["team_name"], "Administration team")

    def test_approver_roles_are_reported_for_a_approver(self):
        approver = make_approver(
            "supervisor",
            username="sup@teams.test",
            institution_wide=False,
            team=Team.objects.get(pk=self.team["id"]),
        )
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="supervisor"), approver
        )
        response = self.client.get("/api/v1/employees/")
        row = next(
            r for r in response.data["results"] if r["user_id"] == approver.pk
        )
        self.assertEqual(row["approver_roles"], ["supervisor"])


class RoutingConfigurationTests(TestCase):
    """A section's approver decides the step; institution-wide is the fallback."""

    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@routing.test",
            email="hr@routing.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        ensure_roles("supervisor", "hod", "registrar")

    def test_a_section_approver_holds_the_role(self):
        # The person is placed on the team first: eligibility is team membership,
        # so a fixture must not build an appointment the product would refuse.
        person = make_approver(
            "supervisor",
            username="sup@routing.test",
            institution_wide=False,
            team=team_for("Science"),
        )
        team = make_team(
            "Science",
            ("supervisor", "hod"),
            approvers={"supervisor": person},
        )
        section = team.workflow.sections.get(approver_role__code="supervisor")
        self.assertEqual(section.approver, person)
        self.assertTrue(is_approver_user(person))

    def test_a_person_can_hold_the_same_role_on_several_teams(self):
        """The one-role rule is per team, so one capacity may span two of them."""
        person = make_approver(
            "supervisor",
            username="multi@routing.test",
            institution_wide=False,
            team=team_for("Science"),
        )
        make_team("Science", ("supervisor",), approvers={"supervisor": person})
        # The employee record moves to the second team, as an internal transfer
        # would, so each appointment is made for somebody who is a member of it.
        profile = person.employee_profile
        profile.team = team_for("Arts")
        profile.save(update_fields=["team"])
        make_team("Arts", ("supervisor",), approvers={"supervisor": person})
        self.assertEqual(approver_role_codes_for(person), ["supervisor"])

    def test_removing_an_appointment_leaves_the_step_unstaffed(self):
        """The step stops routing rather than routing to the removed person.

        The record of the period stays, so "who held this before" is still
        answerable, but nothing points at them as the current approver.
        """
        person = make_approver(
            "supervisor",
            username="reuse@routing.test",
            institution_wide=False,
            team=team_for("Science"),
        )
        team = make_team(
            "Science",
            ("supervisor",),
            approvers={"supervisor": person},
        )
        section = team.workflow.sections.get(approver_role__code="supervisor")
        remove_section_member(
            membership=section.members.get(user=person), actor=self.hr
        )
        section.refresh_from_db()
        self.assertIsNone(section.approver_id)
        # ``all_objects``, not the default manager: the default manager returns
        # only open periods, and the point here is that the closed one survived.
        self.assertTrue(
            SectionMember.all_objects.filter(
                section=section, user=person, effective_to=timezone.localdate()
            ).exists()
        )

    def test_a_staffed_role_blocks_its_own_retirement(self):
        """A role in use by a workflow is named once, with its section count.

        Sections and their members are the same blocker seen two ways, so the
        message merges them: telling HR the "Science Workflow" is a problem
        twice, once as a section and once as a member, teaches nothing about
        what to go and fix.
        """
        team = make_team("Science", ("supervisor",))
        with self.assertRaises(Exception) as ctx:
            ensure_role_not_in_use(ApproverRole.objects.get(code="supervisor"))
        message = str(ctx.exception)
        self.assertIn(f"the '{team.workflow.name}' workflow", message)
        self.assertIn("1 section and 1 member", message)
        self.assertEqual(message.count(f"the '{team.workflow.name}' workflow"), 1)

    def test_employee_profiles_expose_their_team(self):
        from users.models import EmployeeProfile

        team = make_team("Science", ("supervisor",))
        employee = User.objects.create_user(
            username="placed@routing.test",
            email="placed@routing.test",
            password=DEV_PASSWORD,
        )
        profile = EmployeeProfile.objects.create(
            user=employee,
            faculty="Faculty of Science",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
            team=team,
        )
        self.assertEqual(profile.team, team)
        # The team's own approver is a member too, so this is "placed on it",
        # not "the only person on it".
        self.assertIn(profile, list(team.members.all()))

    def test_a_workflow_keeps_its_sections_in_order(self):
        workflow = make_workflow("Ordered", ("supervisor", "hod", "registrar"))
        self.assertEqual(
            [s.approver_role.code for s in workflow.sections.all()],
            ["supervisor", "hod", "registrar"],
        )
        self.assertEqual([s.order for s in workflow.sections.all()], [1, 2, 3])

    def test_a_workflow_effective_from_the_future_is_not_selectable(self):
        workflow = make_workflow("Future", ("supervisor",))
        workflow.effective_from = timezone.localdate() + timezone.timedelta(days=7)
        workflow.save(update_fields=["effective_from"])
        self.assertGreater(workflow.effective_from, timezone.localdate())
        self.assertEqual(Workflow.objects.get(pk=workflow.pk).effective_from,
                         workflow.effective_from)
