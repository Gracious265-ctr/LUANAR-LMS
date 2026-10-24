"""Teams and workflows, scoped to a manager: the team-manager delegation.

A team manager is an ordinary ``employee`` holding a team-wide approver role
flagged as the team's manager. They may configure the team they manage — its
chains, its roster, its approvers — but editing the team's identity, creating
new teams, and retiring one stay HR's. Every read and write is scoped to the
teams they manage, so another team's configuration is a 404, not a 200.

These cover the viewset-level permission and queryset scoping; the finer
per-action refusals live where the services enforce them.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from roles.services import managed_team_ids_for
from teams.models import TeamRoleAssignment

from .testing import DEV_PASSWORD, ensure_roles, make_employee, make_team

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"


def make_manager(team, email: str, *, role_code="supervisor"):
    user = User.objects.create_user(
        username=email,
        email=email,
        password=DEV_PASSWORD,
        first_name="Team",
        last_name="Manager",
        role=User.Role.EMPLOYEE,
    )
    role = ensure_roles(role_code)[role_code]
    TeamRoleAssignment.objects.create(
        team=team, role=role, user=user, is_team_manager=True
    )
    return user


class ManagerAccessBase(TestCase):
    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@manager.test",
            email="hr@manager.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.team = make_team("Managed Team", ("supervisor", "hod"))
        self.other = make_team("Other Team", ("supervisor", "hod"))
        self.manager = make_manager(self.team, "manager@manager.test")
        self.plain = User.objects.create_user(
            username="plain@manager.test",
            email="plain@manager.test",
            password=DEV_PASSWORD,
            role=User.Role.EMPLOYEE,
        )

    def section_ids_for(self, team):
        return set(team.workflow.sections.values_list("id", flat=True))


class ManagerTeamAccessTests(ManagerAccessBase):
    def test_manager_lists_only_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(TEAMS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(ids, {self.team.id})

    def test_manager_reads_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"{TEAMS_URL}{self.team.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_read_another_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"{TEAMS_URL}{self.other.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_cannot_create_a_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "A Brand New Team",
                "new_workflow": {
                    "name": "New Chain",
                    "sections": [
                        {"name": "Supervisor", "approver_role": "supervisor"}
                    ],
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_edit_a_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            f"{TEAMS_URL}{self.team.id}/", {"name": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_retire_a_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(f"{TEAMS_URL}{self.team.id}/deactivate/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.team.refresh_from_db()
        self.assertNotEqual(self.team.status, "inactive")

    def test_manager_may_check_their_own_team_readiness(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(f"{TEAMS_URL}{self.team.id}/validate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_plain_employee_is_refused(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(
            self.client.get(TEAMS_URL).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hr_still_sees_every_team(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(TEAMS_URL)
        ids = {row["id"] for row in response.data["results"]}
        self.assertGreaterEqual(ids, {self.team.id, self.other.id})


class ManagerWorkflowAccessTests(ManagerAccessBase):
    def test_manager_sees_only_their_team_workflows(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(WORKFLOWS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        team_ids = {row["team"] for row in response.data["results"]}
        self.assertEqual(team_ids, {self.team.id})

    def test_manager_cannot_read_another_teams_workflow(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"{WORKFLOWS_URL}{self.other.workflow_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_creates_a_workflow_for_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            WORKFLOWS_URL,
            {"name": "Replacement chain", "team": self.team.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["team"], self.team.id)

    def test_manager_cannot_create_a_workflow_for_another_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            WORKFLOWS_URL,
            {"name": "Hijack", "team": self.other.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("permission", str(response.data).lower())


class ManagerSectionMemberAccessTests(ManagerAccessBase):
    def test_manager_sees_only_their_team_appointments(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/v1/section-members/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned = {row["section"] for row in response.data["results"]}
        self.assertTrue(returned)  # the fixture team is staffed
        self.assertTrue(
            returned.issubset(self.section_ids_for(self.team))
        )
        self.assertFalse(returned & self.section_ids_for(self.other))


class ManagerEligibleApproversTests(ManagerAccessBase):
    def test_manager_may_query_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}eligible-approvers/", {"team": self.team.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_query_another_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}eligible-approvers/", {"team": self.other.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data)


class ManagerMemberCandidatesTests(ManagerAccessBase):
    """The roster's candidate feed, read by a manager rather than the HR directory.

    The HR directory is ``IsHRRole``, so a manager building their roster had no
    way to read who was available. This is the same list through a route scoped to
    the team the manager runs: unassigned, matching category, and not a wide
    approver for the team.
    """

    def setUp(self):
        super().setUp()
        # An unassigned administration employee is a candidate for an
        # administration team; an academic one is not.
        self.candidate = make_employee("candidate@manager.test")
        self.academic = make_employee(
            "academic@manager.test",
            category="academic",
        )

    def test_manager_reads_their_own_teams_candidates(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.id}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.data}
        self.assertIn(self.candidate.email, emails)
        # The team's own category only, and never an already-placed employee.
        self.assertNotIn(self.academic.email, emails)

    def test_candidates_exclude_the_wide_approvers_of_the_team(self):
        # The manager holds a team-wide role and must not be offered as a roster
        # candidate: a wide approver serves steps, not the roster.
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.id}/member-candidates/"
        )
        emails = {row["email"] for row in response.data}
        self.assertNotIn(self.manager.email, emails)

    def test_manager_cannot_read_another_teams_candidates(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}{self.other.id}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_reads_candidates_too(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.id}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_plain_employee_is_refused(self):
        self.client.force_authenticate(self.plain)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.id}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ManagerSectionMemberWriteTests(ManagerAccessBase):
    """A manager staffs the steps of a team they run, and only those.

    The list read is scoped by the viewset queryset, but a write names its section
    directly, so the scope is re-asserted on the serializer: without it a manager
    could appoint somebody to any team's step by id.
    """

    MEMBERS_URL = "/api/v1/section-members/"

    def setUp(self):
        super().setUp()
        # An approver must be a member of the team the step belongs to, so the
        # person a manager would appoint is first placed on the team — which is
        # exactly the roster step the member-candidates feed exists to serve.
        self.staff = make_employee("staff@manager.test", team=self.team)
        self.other_staff = make_employee("other-staff@manager.test", team=self.other)
        self.own_section = self.team.workflow.sections.order_by("order").last()
        self.other_section = self.other.workflow.sections.order_by("order").last()

    def test_manager_may_staff_a_step_of_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.MEMBERS_URL,
            {"section": self.own_section.id, "user": self.staff.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.own_section.refresh_from_db()
        self.assertEqual(self.own_section.approver_id, self.staff.id)

    def test_manager_cannot_staff_another_teams_step(self):
        self.client.force_authenticate(self.manager)
        previous = self.other_section.approver_id
        response = self.client.post(
            self.MEMBERS_URL,
            {"section": self.other_section.id, "user": self.other_staff.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.other_section.refresh_from_db()
        self.assertEqual(self.other_section.approver_id, previous)

    def test_hr_may_staff_any_step(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post(
            self.MEMBERS_URL,
            {"section": self.other_section.id, "user": self.other_staff.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class ManagerApproverRoleListTests(ManagerAccessBase):
    """The read-only role list a manager describes a chain's steps with.

    The role endpoint proper is HR-only, so the workflow form opened with no roles
    for a manager and could not describe a step. This exposes the active roles
    read-only to whoever manages a team; writing roles stays HR's.
    """

    ROLES_URL = f"{TEAMS_URL}eligible-approver-roles/"

    def test_manager_reads_the_active_roles(self):
        ensure_roles("supervisor", "hod")
        self.client.force_authenticate(self.manager)
        response = self.client.get(self.ROLES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {row["code"] for row in response.data}
        self.assertGreaterEqual(codes, {"supervisor", "hod"})

    def test_retired_roles_are_not_offered(self):
        roles = ensure_roles("supervisor", "hod")
        roles["hod"].is_active = False
        roles["hod"].save(update_fields=["is_active"])
        self.client.force_authenticate(self.manager)
        response = self.client.get(self.ROLES_URL)
        codes = {row["code"] for row in response.data}
        self.assertNotIn("hod", codes)

    def test_hr_reads_them_too(self):
        ensure_roles("supervisor")
        self.client.force_authenticate(self.hr)
        self.assertEqual(
            self.client.get(self.ROLES_URL).status_code, status.HTTP_200_OK
        )

    def test_plain_employee_is_refused(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(
            self.client.get(self.ROLES_URL).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class SuperuserConfigAccessTests(ManagerAccessBase):
    """A superuser is the bootstrap administrator: HR-equivalent here."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(
            username="admin@manager.test",
            email="admin@manager.test",
            password=DEV_PASSWORD,
        )

    def test_superuser_sees_every_team(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(TEAMS_URL)
        ids = {row["id"] for row in response.data["results"]}
        self.assertGreaterEqual(ids, {self.team.id, self.other.id})

    def test_superuser_reaches_the_organisation_config(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get("/api/v1/campuses/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get("/api/v1/approver-roles/").status_code,
            status.HTTP_200_OK,
        )

    def test_superuser_may_create_a_team(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            TEAMS_URL,
            {
                "name": "Admin Team",
                "new_workflow": {
                    "name": "Admin Chain",
                    "sections": [
                        {"name": "Supervisor", "approver_role": "supervisor"}
                    ],
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class ManagerDesignationTests(ManagerAccessBase):
    """The set-manager/clear-manager actions, and the flag they report.

    The designation itself is a service rule — one manager per team — and these
    cover the two things the frontend depends on: the action endpoints exist and
    are HR-only, and the holding's payload says whether it carries the flag.
    """

    ASSIGNMENTS_URL = "/api/v1/team-role-assignments/"

    def setUp(self):
        super().setUp()
        hod = ensure_roles("hod")["hod"]
        self.deputy = User.objects.create_user(
            username="deputy@manager.test",
            email="deputy@manager.test",
            password=DEV_PASSWORD,
            role=User.Role.EMPLOYEE,
        )
        self.deputy_holding = TeamRoleAssignment.objects.create(
            team=self.team, role=hod, user=self.deputy
        )
        self.existing_manager = TeamRoleAssignment.objects.get(
            team=self.team, user=self.manager
        )

    def test_payload_reports_whether_a_holding_is_the_manager(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get(self.ASSIGNMENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_id = {row["id"]: row for row in response.data["results"]}
        self.assertTrue(by_id[self.existing_manager.id]["is_team_manager"])
        self.assertFalse(by_id[self.deputy_holding.id]["is_team_manager"])

    def test_set_manager_designates_a_holding_and_replaces_the_previous_one(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post(
            f"{self.ASSIGNMENTS_URL}{self.deputy_holding.id}/set-manager/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_team_manager"])

        self.existing_manager.refresh_from_db()
        self.assertFalse(self.existing_manager.is_team_manager)
        self.deputy_holding.refresh_from_db()
        self.assertTrue(self.deputy_holding.is_team_manager)

    def test_clear_manager_drops_the_flag_but_keeps_the_holding(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post(
            f"{self.ASSIGNMENTS_URL}{self.existing_manager.id}/clear-manager/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_team_manager"])

        self.existing_manager.refresh_from_db()
        self.assertFalse(self.existing_manager.is_team_manager)
        self.assertTrue(
            TeamRoleAssignment.objects.filter(pk=self.existing_manager.pk).exists()
        )

    def test_a_manager_cannot_designate_a_manager(self):
        # Writing a team-wide holding is HR's, like every write under
        # team-role-assignments: a manager configures the team they run, not who
        # runs it.
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"{self.ASSIGNMENTS_URL}{self.deputy_holding.id}/set-manager/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ManagerScopingHelperTests(ManagerAccessBase):
    def test_helper_matches_the_viewset_scope(self):
        self.assertEqual(managed_team_ids_for(self.manager), [self.team.id])
        self.assertEqual(managed_team_ids_for(self.plain), [])
        self.assertEqual(managed_team_ids_for(self.hr), [])
