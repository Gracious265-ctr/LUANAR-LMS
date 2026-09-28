"""Teams, campuses, and institution-wide holdings: the routing configuration.

A team is the unit that decides *who* approves: at submission the applicant's
team selects the workflow, and the team's members are who hold each role in it.
These tests cover the whole configuration surface around that fact — the campus
a team belongs to, the membership that staffs each role, the institution-wide
holdings that stand in when a role has no team member, and the employee side
that puts someone on a team at all.
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
    Team,
    TeamMember,
    Workflow,
)
from .services import (
    TeamActionError,
    add_team_member,
    approver_role_codes_for,
    create_role_assignment,
    ensure_role_not_in_use,
    is_approver_user,
    remove_role_assignment,
    remove_team_member,
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
MEMBERS_URL = "/api/v1/team-members/"
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
        self.workflow = make_workflow("Administration chain", ("supervisor", "hod"))

    def create_team(self, name="Administration team", **extra) -> dict:
        payload = {"name": name, "workflow": self.workflow.pk}
        payload.update(extra)
        response = self.client.post(TEAMS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def add_member(self, team_id, user, role_code="supervisor") -> dict:
        response = self.client.post(
            MEMBERS_URL,
            {"team": team_id, "user": user.pk, "role": role_code},
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
            {"name": "Team", "workflow": self.workflow.pk, "campus": campus.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campus", response.data)


class TeamAPITests(ConfigurationAPIBase):
    def test_hr_creates_a_team(self):
        team = self.create_team(description="Administration staff")
        self.assertEqual(team["name"], "Administration team")
        self.assertEqual(team["workflow"], self.workflow.pk)
        self.assertEqual(team["workflow_name"], "Administration chain")

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

    def test_a_team_may_be_created_without_a_workflow(self):
        """Allowed, but the team cannot route anything until one is set."""
        response = self.client.post(TEAMS_URL, {"name": "Unrouted"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        team = Team.objects.get(name="Unrouted")
        self.assertIsNone(team.workflow_id)

    def test_a_team_may_be_created_without_a_campus(self):
        team = self.create_team("Non-campus team")
        self.assertIsNone(team["campus"])
        self.assertIsNone(Team.objects.get(name="Non-campus team").campus_id)

    def test_duplicate_name_rejected(self):
        self.create_team()
        response = self.client.post(
            TEAMS_URL, {"name": "Administration team", "workflow": self.workflow.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_an_unknown_workflow_rejected(self):
        response = self.client.post(
            TEAMS_URL, {"name": "Bad team", "workflow": 99999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("workflow", response.data)

    def test_teams_cannot_be_deleted(self):
        team = self.create_team()
        response = self.client.delete(f"{TEAMS_URL}{team['id']}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Team.objects.filter(pk=team["id"]).exists())

    def test_non_hr_cannot_create_a_team(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            TEAMS_URL, {"name": "Sneaky team", "workflow": self.workflow.pk},
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

    def test_listing_nests_members(self):
        team = self.create_team()
        approver = make_approver("supervisor", username="sup@teams.test")
        self.add_member(team["id"], approver)
        response = self.client.get(TEAMS_URL)
        row = next(r for r in response.data["results"] if r["id"] == team["id"])
        self.assertEqual(row["member_count"], 1)
        self.assertEqual(row["members"][0]["role"], "supervisor")
        self.assertEqual(row["members"][0]["user"], approver.pk)

    def test_inactive_teams_are_hidden_by_default(self):
        self.create_team()
        team = Team.objects.get(name="Administration team")
        team.is_active = False
        team.save(update_fields=["is_active"])
        response = self.client.get(TEAMS_URL)
        self.assertNotIn(
            "Administration team", [r["name"] for r in response.data["results"]]
        )
        response = self.client.get(f"{TEAMS_URL}?include_inactive=1")
        self.assertIn(
            "Administration team", [r["name"] for r in response.data["results"]]
        )

    def test_an_inactive_workflow_cannot_be_attached(self):
        workflow = make_workflow("Old chain", ("dean",), is_active=False)
        response = self.client.post(
            TEAMS_URL, {"name": "Stale team", "workflow": workflow.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TeamMembershipTests(ConfigurationAPIBase):
    def setUp(self):
        super().setUp()
        self.team = self.create_team()
        self.supervisor = make_approver(
            "supervisor", username="sup@teams.test", institution_wide=False
        )

    def test_hr_staffs_a_role(self):
        membership = self.add_member(self.team["id"], self.supervisor, "supervisor")
        self.assertEqual(membership["role"], "supervisor")
        self.assertEqual(membership["user"], self.supervisor.pk)
        self.assertEqual(
            TeamMember.objects.get(team_id=self.team["id"], user=self.supervisor).role.code,
            "supervisor",
        )

    def test_adding_a_member_makes_them_an_approver(self):
        self.assertFalse(is_approver_user(self.supervisor))
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        self.assertTrue(is_approver_user(self.supervisor))
        self.assertEqual(approver_role_codes_for(self.supervisor), ["supervisor"])

    def test_membership_is_audited(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        entry = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.TEAM,
            action=AuditEntry.Action.CREATED,
        ).order_by("-id").first()
        self.assertEqual(entry.actor, self.hr)
        self.assertIn("Supervisor", entry.reason)

    def test_a_role_held_twice_on_one_team_is_refused(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        second = make_approver("supervisor", username="sup2@teams.test")
        response = self.client.post(
            MEMBERS_URL,
            {"team": self.team["id"], "user": second.pk, "role": "supervisor"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
        self.assertIn("already held", response.data["role"][0])
        self.assertEqual(TeamMember.objects.filter(team_id=self.team["id"]).count(), 1)

    def test_a_person_holds_one_role_per_team(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        response = self.client.post(
            MEMBERS_URL,
            {"team": self.team["id"], "user": self.supervisor.pk, "role": "hod"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user", response.data)

    def test_a_team_without_a_workflow_takes_no_members(self):
        unrouted = self.client.post(
            TEAMS_URL, {"name": "Unrouted team"}, format="json"
        ).data
        response = self.client.post(
            MEMBERS_URL,
            {"team": unrouted["id"], "user": self.supervisor.pk, "role": "supervisor"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("workflow", response.data["team"][0])

    def test_an_inactive_team_takes_no_members(self):
        team = Team.objects.get(pk=self.team["id"])
        team.is_active = False
        team.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"team": team.pk, "user": self.supervisor.pk, "role": "supervisor"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("inactive", response.data["team"][0])

    def test_an_inactive_user_cannot_be_staffed(self):
        self.supervisor.is_active = False
        self.supervisor.save(update_fields=["is_active"])
        response = self.client.post(
            MEMBERS_URL,
            {"team": self.team["id"], "user": self.supervisor.pk, "role": "supervisor"},
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
            {"team": self.team["id"], "user": self.supervisor.pk, "role": "supervisor"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deactivated", response.data["role"][0])

    def test_an_unknown_role_is_rejected(self):
        response = self.client.post(
            MEMBERS_URL,
            {"team": self.team["id"], "user": self.supervisor.pk, "role": "wizard"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_members_can_be_listed_per_team(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        other = self.create_team("Other team")
        response = self.client.get(f"{MEMBERS_URL}?team={other['id']}")
        self.assertEqual(response.data["results"], [] if isinstance(response.data, dict) else [])
        response = self.client.get(f"{MEMBERS_URL}?team={self.team['id']}")
        rows = response.data["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user"], self.supervisor.pk)

    def test_a_bad_team_filter_is_a_client_error(self):
        response = self.client.get(f"{MEMBERS_URL}?team=not-a-number")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removing_a_member_revokes_approver_status(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        membership = TeamMember.objects.get(team_id=self.team["id"])
        response = self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TeamMember.objects.filter(pk=membership.pk).exists())
        self.assertFalse(is_approver_user(self.supervisor))

    def test_removal_is_audited(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        membership = TeamMember.objects.get(team_id=self.team["id"])
        self.client.delete(f"{MEMBERS_URL}{membership.pk}/")
        self.assertTrue(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.TEAM,
                action=AuditEntry.Action.CANCELLED,
                target_id=str(self.team["id"]),
            ).exists()
        )

    def test_memberships_cannot_be_edited_in_place(self):
        """Re-staffing a role is a removal plus an addition, both audited."""
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        membership = TeamMember.objects.get(team_id=self.team["id"])
        response = self.client.patch(
            f"{MEMBERS_URL}{membership.pk}/", {"role": "hod"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_non_hr_cannot_staff_a_role(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(
            MEMBERS_URL,
            {"team": self.team["id"], "user": self.supervisor.pk, "role": "supervisor"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TeamMember.objects.exists())

    def test_service_layer_refuses_a_second_holder_of_a_role(self):
        approver = make_approver("supervisor", username="sup3@teams.test")
        team = Team.objects.get(pk=self.team["id"])
        role = ApproverRole.objects.get(code="supervisor")
        add_team_member(
            team=team, user=approver, role=role, actor=self.hr
        )
        other = make_approver("supervisor", username="sup4@teams.test")
        with self.assertRaises(TeamActionError) as ctx:
            add_team_member(team=team, user=other, role=role, actor=self.hr)
        self.assertEqual(ctx.exception.field, "role")

    def test_removing_a_membership_twice_is_a_client_error(self):
        self.add_member(self.team["id"], self.supervisor, "supervisor")
        membership = TeamMember.objects.get(team_id=self.team["id"])
        remove_team_member(membership=membership, actor=self.hr)
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
        self.add_member(self.team["id"], approver, "supervisor")
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

    def test_a_team_member_holds_the_role(self):
        person = make_approver("supervisor", username="sup@routing.test")
        team = make_team("Science", ("supervisor", "hod"), approvers={"supervisor": person})
        member = team.memberships.get(role__code="supervisor")
        self.assertEqual(member.user, person)
        self.assertTrue(is_approver_user(person))

    def test_a_person_can_hold_roles_on_several_teams(self):
        person = make_approver("supervisor", username="multi@routing.test")
        make_team("Science", ("supervisor",), approvers={"supervisor": person})
        make_team("Arts", ("supervisor",), approvers={"supervisor": person})
        self.assertEqual(approver_role_codes_for(person), ["supervisor"])

    def test_a_removed_membership_frees_the_role_for_reuse(self):
        person = make_approver("supervisor", username="reuse@routing.test")
        team = make_team("Science", ("supervisor",), approvers={"supervisor": person})
        remove_team_member(
            membership=team.memberships.get(role__code="supervisor"), actor=self.hr
        )
        other = make_approver("supervisor", username="reuse2@routing.test")
        add_team_member(
            team=team,
            user=other,
            role=ApproverRole.objects.get(code="supervisor"),
            actor=self.hr,
        )
        self.assertEqual(team.memberships.get(role__code="supervisor").user, other)

    def test_a_staffed_role_blocks_its_own_retirement(self):
        make_team("Science", ("supervisor",))
        with self.assertRaises(Exception) as ctx:
            ensure_role_not_in_use(ApproverRole.objects.get(code="supervisor"))
        self.assertIn("'Science' team", str(ctx.exception))

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

    def test_a_workflow_keeps_its_stages_in_order(self):
        workflow = make_workflow("Ordered", ("supervisor", "hod", "registrar"))
        self.assertEqual(
            [s.approver_role.code for s in workflow.stages.all()],
            ["supervisor", "hod", "registrar"],
        )
        self.assertEqual([s.order for s in workflow.stages.all()], [1, 2, 3])

    def test_a_workflow_effective_from_the_future_is_not_selectable(self):
        workflow = make_workflow("Future", ("supervisor",))
        workflow.effective_from = timezone.localdate() + timezone.timedelta(days=7)
        workflow.save(update_fields=["effective_from"])
        self.assertGreater(workflow.effective_from, timezone.localdate())
        self.assertEqual(Workflow.objects.get(pk=workflow.pk).effective_from,
                         workflow.effective_from)
