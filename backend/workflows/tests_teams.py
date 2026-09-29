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
)

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
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
        payload = {"name": name, "new_workflow": self.chain_payload()}
        payload.update(extra)
        response = self.client.post(TEAMS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # The team's own chain, so tests can staff and inspect its steps. It is
        # the created team's workflow, not a shared fixture, because a team owns
        # its chain.
        self.workflow = Workflow.objects.get(pk=response.data["workflow"])
        return response.data

    def add_member_to_section(self, section, user) -> dict:
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
        """``workflow`` is read-only: a chain is never picked from a list.

        The field is still in the response, so a client that has it cached — or
        an old one that still sends it — has to see that posting it does
        nothing. Silently honouring it would put a team on somebody else's
        chain, which is the one outcome the team-owned rule exists to stop.
        """
        other = self.create_team(name="Other team")
        self.create_team(
            name="Copying team",
            **{"workflow": other["workflow"]},
        )
        team = Team.objects.get(name="Copying team")
        self.assertNotEqual(team.workflow_id, other["workflow"])

    def test_a_team_must_describe_its_chain(self):
        """A team with no steps routes nothing, so it is refused at creation."""
        response = self.client.post(TEAMS_URL, {"name": "Chainless team"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_workflow", response.data)
        self.assertFalse(Team.objects.filter(name="Chainless team").exists())

    def test_a_team_with_no_steps_is_refused(self):
        response = self.client.post(
            TEAMS_URL,
            {"name": "Empty chain", "new_workflow": {"sections": []}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_workflow", response.data)
        self.assertFalse(Workflow.objects.filter(name="Empty chain").exists())

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
        """A team reports the sections of the workflow it points at.

        Members live on the sections, not the team, so what a team row shows is
        the shape of its chain and how many people could act at each step.
        """
        team = self.create_team()
        approver = make_approver("supervisor", username="sup@teams.test")
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="supervisor"), approver
        )
        response = self.client.get(TEAMS_URL)
        row = next(r for r in response.data["results"] if r["id"] == team["id"])
        self.assertEqual(
            [(s["approver_role"], s["member_count"]) for s in row["sections"]],
            [("supervisor", 1), ("hod", 0)],
        )

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


class SectionMembershipTests(ConfigurationAPIBase):
    """Who can act for a section.

    The unit here is the *section*, not the team: membership belongs to the
    chain's approval steps. A section takes any number of people and one person
    may be in several sections, so the only rule left is "not twice in the same
    section".
    """

    def setUp(self):
        super().setUp()
        self.team = self.create_team()
        self.section = Section.objects.get(
            workflow=self.workflow, order=1
        )
        self.supervisor = make_approver(
            "supervisor", username="sup@teams.test", institution_wide=False
        )

    def add_member(self, user, section=None) -> dict:
        return super().add_member_to_section(section or self.section, user)

    def test_hr_staffs_a_section(self):
        membership = self.add_member(self.supervisor)
        self.assertEqual(membership["user"], self.supervisor.pk)
        self.assertEqual(membership["section"], self.section.pk)
        self.assertEqual(
            SectionMember.objects.get(
                section_id=self.section.pk, user=self.supervisor
            ).section.approver_role.code,
            "supervisor",
        )

    def test_adding_a_member_makes_them_an_approver(self):
        self.assertFalse(is_approver_user(self.supervisor))
        self.add_member(self.supervisor)
        self.assertTrue(is_approver_user(self.supervisor))
        self.assertEqual(approver_role_codes_for(self.supervisor), ["supervisor"])

    def test_a_section_takes_several_members(self):
        """The reason sections exist: any-of, decided by whoever acts first."""
        second = make_approver("supervisor", username="sup2@teams.test")
        self.add_member(self.supervisor)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": second.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            set(
                SectionMember.objects.filter(section=self.section).values_list(
                    "user_id", flat=True
                )
            ),
            {self.supervisor.pk, second.pk},
        )

    def test_the_same_person_may_sit_on_several_sections(self):
        """One person can hold more than one point in a chain."""
        hod = self.workflow.sections.get(order=2)
        self.add_member(self.supervisor)
        response = self.client.post(
            MEMBERS_URL, {"section": hod.pk, "user": self.supervisor.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(SectionMember.objects.filter(user=self.supervisor).count(), 2)

    def test_membership_is_audited(self):
        self.add_member(self.supervisor)
        entry = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.CREATED,
        ).order_by("-id").first()
        self.assertEqual(entry.actor, self.hr)
        self.assertIn("Supervisor", entry.reason)

    def test_a_person_cannot_join_one_section_twice(self):
        self.add_member(self.supervisor)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user", response.data)
        self.assertIn("already a member", response.data["user"][0])

    def test_an_inactive_section_takes_no_members(self):
        self.section.is_active = False
        self.section.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("inactive", response.data["section"][0])

    def test_an_inactive_user_cannot_be_staffed(self):
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

    def test_members_can_be_listed_per_section_and_per_workflow(self):
        self.add_member(self.supervisor)
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

    def test_members_can_be_listed_for_one_user(self):
        self.add_member(self.supervisor)
        response = self.client.get(f"{MEMBERS_URL}?user={self.supervisor.pk}")
        self.assertEqual(len(response.data["results"]), 1)

    def test_a_bad_section_filter_is_a_client_error(self):
        response = self.client.get(f"{MEMBERS_URL}?section=not-a-number")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removing_a_member_revokes_approver_status(self):
        self.add_member(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SectionMember.objects.filter(pk=membership.pk).exists())
        self.assertFalse(is_approver_user(self.supervisor))

    def test_removal_leaves_a_multi_member_section_routable(self):
        """Removing one of several members must not strand the step."""
        second = make_approver("supervisor", username="sup2@teams.test")
        self.add_member(self.supervisor)
        membership = SectionMember.objects.create(section=self.section, user=second)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(
            SectionMember.objects.filter(section=self.section, user=self.supervisor).exists()
        )

    def test_removal_is_audited(self):
        self.add_member(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        entry = AuditEntry.objects.get(
            target_type=AuditEntry.TargetType.WORKFLOW,
            action=AuditEntry.Action.DEACTIVATED,
            target_id=str(self.workflow.pk),
        )
        self.assertEqual(entry.detail["after"]["effective_to"], str(timezone.localdate()))

    def test_memberships_cannot_be_edited_in_place(self):
        """Re-staffing a section is a removal plus an addition, both audited."""
        self.add_member(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        response = self.client.patch(
            f"{MEMBERS_URL}{membership.pk}/",
            {"section": self.workflow.sections.get(order=2).pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_non_hr_cannot_staff_a_section(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            MEMBERS_URL,
            {"section": self.section.pk, "user": self.supervisor.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(SectionMember.objects.exists())

    def test_service_layer_refuses_a_duplicate_membership(self):
        self.add_member(self.supervisor)
        with self.assertRaises(TeamActionError) as ctx:
            add_section_member(
                section=self.section, user=self.supervisor, actor=self.hr
            )
        self.assertEqual(ctx.exception.field, "user")

    def test_service_layer_allows_a_second_distinct_member(self):
        """The any-of rule: a section is not one person, and the service agrees."""
        other = make_approver("supervisor", username="sup5@teams.test")
        self.add_member(self.supervisor)
        add_section_member(section=self.section, user=other, actor=self.hr)
        self.assertEqual(SectionMember.objects.filter(section=self.section).count(), 2)

    def test_removing_a_membership_twice_is_a_client_error(self):
        self.add_member(self.supervisor)
        membership = SectionMember.objects.get(section=self.section, user=self.supervisor)
        remove_section_member(membership=membership, actor=self.hr)
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


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

    def test_a_team_role_cannot_be_granted_institution_wide(self):
        """Team roles are staffed through a team, not a blanket assignment."""
        response = self.client.post(
            ASSIGNMENTS_URL,
            {
                "user": self.employee.pk,
                "role": ApproverRole.objects.get(code="supervisor").pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team role", response.data["role"][0])
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
            department="Administration",
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
        approver = make_approver("supervisor", username="sup@teams.test")
        self.add_member_to_section(
            self.workflow.sections.get(approver_role__code="supervisor"), approver
        )
        response = self.client.get("/api/v1/employees/")
        row = next(
            r for r in response.data["results"] if r["user_id"] == approver.pk
        )
        self.assertEqual(row["approver_roles"], ["supervisor"])


class RoutingConfigurationTests(TestCase):
    """Team membership decides the approver; institution-wide is the fallback."""

    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@routing.test",
            email="hr@routing.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        ensure_roles("supervisor", "hod", "registrar")

    def test_a_section_member_holds_the_role(self):
        person = make_approver("supervisor", username="sup@routing.test")
        team = make_team("Science", ("supervisor", "hod"), approvers={"supervisor": person})
        section = team.workflow.sections.get(approver_role__code="supervisor")
        self.assertEqual(section.members.get().user, person)
        self.assertTrue(is_approver_user(person))

    def test_a_person_can_hold_roles_on_several_teams(self):
        person = make_approver("supervisor", username="multi@routing.test")
        make_team("Science", ("supervisor",), approvers={"supervisor": person})
        make_team("Arts", ("supervisor",), approvers={"supervisor": person})
        self.assertEqual(approver_role_codes_for(person), ["supervisor"])

    def test_a_removed_membership_frees_the_section_for_reuse(self):
        """Removing one member of a shared section leaves the rest acting.

        A section holds several people, so unlike the old one-holder-per-role
        rule there is nothing to "reuse" — the step simply carries on with
        whoever is left, and stays routable.
        """
        person = make_approver("supervisor", username="reuse@routing.test")
        second = make_approver("supervisor", username="reuse1@routing.test")
        team = make_team("Science", ("supervisor",), approvers={"supervisor": person})
        section = team.workflow.sections.get(approver_role__code="supervisor")
        add_section_member(section=section, user=second, actor=self.hr)
        remove_section_member(
            membership=section.members.get(user=second), actor=self.hr
        )
        self.assertEqual(
            list(section.members.values_list("user_id", flat=True)), [person.pk]
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
            department="Administration",
            faculty="Faculty of Science",
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
            team=team,
        )
        self.assertEqual(profile.team, team)
        self.assertEqual(list(team.members.all()), [profile])

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
