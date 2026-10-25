"""Team-management delegation: what a team's designated manager may do.

HR creates a team and assigns a team-wide approver; flagging that holding as the
team's manager hands the day-to-day to them — members and workflows — while HR
keeps the team's identity and lifecycle. These tests pin the boundary: the
manager reaches their own team and nothing else, and the operations HR keeps to
itself refuse the manager at the endpoint *and* in the service.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from teams.models import Team, TeamRoleAssignment
from roles.services import (
    WorkflowMemberError,
    add_team_member,
    clear_team_manager,
    create_team_role_assignment,
    is_team_manager,
    set_team_manager,
    team_manager_profile,
)
from chains.models import Workflow

from .testing import DEV_PASSWORD, ensure_roles, make_employee, make_team

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"
TEAM_ROLE_ASSIGNMENTS_URL = "/api/v1/team-role-assignments/"
APPROVER_ROLES_URL = "/api/v1/approver-roles/"


class TeamManagementDelegationTests(TestCase):
    """A manager manages their own team; HR keeps the rest."""

    def setUp(self):
        self.client = APIClient()
        self.hr = User.objects.create_user(
            username="hr@tm.test",
            email="hr@tm.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        self.team_a = make_team("Registry Team", ("supervisor",))
        self.team_b = make_team("Bursar Team", ("supervisor",))

        self.manager = make_employee("manager@tm.test", team=None)
        self.member = make_employee("member@tm.test", team=None)
        self.outsider = make_employee("outsider@tm.test", team=None)

        role = ensure_roles("hod")["hod"]
        self.holding = create_team_role_assignment(
            team=self.team_a,
            role=role,
            user=self.manager,
            actor=self.hr,
            is_team_manager=True,
        )

    def test_manager_is_designated_on_their_team_only(self):
        self.assertTrue(is_team_manager(self.manager, self.team_a))
        self.assertFalse(is_team_manager(self.manager, self.team_b))

    def _as_manager(self):
        self.client.force_authenticate(self.manager)

    def _as(self, user):
        self.client.force_authenticate(user)

    # --- members -----------------------------------------------------------

    def test_manager_adds_a_member_to_their_team(self):
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.employee_profile.team_id, self.team_a.pk)

    def test_manager_designated_by_hrs_create_can_add_members(self):
        # The real flow: HR creates the team and hands it over in one request,
        # then that person — never touched by a test helper — adds a member.
        # Designating the manager by hand and then calling the members action
        # would not catch a handover that fails to leave them managing anything.
        holder = make_employee("handed-over@tm.test", team=None)
        subject = make_employee("handed-over-member@tm.test", team=None)
        self._as(self.hr)
        created = self.client.post(
            TEAMS_URL,
            {
                "name": "Handed-over Team",
                "manager": {"role": ensure_roles("hod")["hod"].pk, "user": holder.pk},
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertTrue(is_team_manager(holder, Team.objects.get(pk=created.data["id"])))

        self._as(holder)
        response = self.client.post(
            f"{TEAMS_URL}{created.data['id']}/members/",
            {"user": subject.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        subject.refresh_from_db()
        self.assertEqual(
            subject.employee_profile.team_id, created.data["id"]
        )

    def test_manager_cannot_add_a_member_to_another_team(self):
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_b.pk}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        # The team is scoped out of the manager's queryset, so it 404s.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_manager_cannot_add_a_member(self):
        self._as(self.outsider)
        url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_member_of_the_managers_category_is_added(self):
        # The roster is measured against the manager's own category, and this
        # member is of it.
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_a_member_of_another_category_is_refused(self):
        # An academic employee is not of the manager's administration category,
        # so the write is refused rather than placing them on the roster.
        academic = make_employee(
            "academic@tm.test", team=None, category="academic"
        )
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        response = self.client.post(url, {"user": academic.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Administration", str(response.data))

    def test_the_candidates_offered_are_the_managers_category(self):
        # The picker offers who the write above would accept: this manager's
        # category, and no other.
        academic = make_employee(
            "academic@tm.test", team=None, category="academic"
        )
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/member-candidates/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offered = {row["id"] for row in response.data}
        self.assertIn(self.member.pk, offered)
        self.assertNotIn(academic.pk, offered)

    def test_a_team_without_a_manager_falls_back_to_its_own_category(self):
        # Before the handover there is no manager to measure against, so the
        # team's own category stands in and HR may still fill the roster. This
        # is reached in the service, because the endpoint itself belongs to the
        # manager and refuses HR outright.
        team = make_team("Draft Team", ("supervisor",))
        self.assertIsNone(team_manager_profile(team))
        academic = make_employee(
            "draft-academic@tm.test", team=None, category="academic"
        )
        with self.assertRaises(WorkflowMemberError) as caught:
            add_team_member(team=team, user=academic, actor=self.hr)
        self.assertIn("Academic", str(caught.exception))

    def test_manager_removes_a_member(self):
        add_team_member(team=self.team_a, user=self.member, actor=self.hr)
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/members/{self.member.pk}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.employee_profile.team_id)

    # --- team details and lifecycle stay with HR ---------------------------

    def test_manager_cannot_edit_team_details(self):
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/"
        response = self.client.patch(url, {"description": "renamed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_retire_a_team(self):
        """Retirement stays with HR, like every other team-wide decision."""
        self._as_manager()
        url = f"{TEAMS_URL}{self.team_a.pk}/deactivate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_still_edits_team_details(self):
        self._as(self.hr)
        url = f"{TEAMS_URL}{self.team_a.pk}/"
        response = self.client.patch(url, {"description": "by hr"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- workflows ---------------------------------------------------------

    def test_manager_creates_a_workflow_on_their_team(self):
        self._as_manager()
        payload = {
            "team": self.team_a.pk,
            "name": "Registry replacement chain",
            "sections": [
                {"name": "Supervisor", "approver_role": "supervisor", "order": 1}
            ],
        }
        response = self.client.post(WORKFLOWS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        workflow = Workflow.objects.get(pk=response.data["id"])
        self.assertEqual(workflow.team_id, self.team_a.pk)

    def test_manager_cannot_create_a_workflow_on_another_team(self):
        self._as_manager()
        payload = {
            "team": self.team_b.pk,
            "name": "Bursar chain",
            "sections": [
                {"name": "Supervisor", "approver_role": "supervisor", "order": 1}
            ],
        }
        response = self.client.post(WORKFLOWS_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_refuses_a_manager_writing_another_team(self):
        with self.assertRaises(WorkflowMemberError):
            add_team_member(team=self.team_b, user=self.member, actor=self.manager)

    # --- approver roles: manager may create, HR retires --------------------

    def test_manager_creates_an_approver_role(self):
        self._as_manager()
        response = self.client.post(
            APPROVER_ROLES_URL, {"label": "Dean of Students"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_manager_cannot_retire_an_approver_role(self):
        self._as_manager()
        created = self.client.post(
            APPROVER_ROLES_URL, {"label": "Director of ICT"}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        url = f"{APPROVER_ROLES_URL}{created.data['id']}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- one manager per team ---------------------------------------------

    def test_one_manager_per_team(self):
        other_holder = make_employee("second-manager@tm.test", team=None)
        role = ensure_roles("dean")["dean"]
        second = create_team_role_assignment(
            team=self.team_a,
            role=role,
            user=other_holder,
            actor=self.hr,
            is_team_manager=True,
        )
        self.holding.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(second.is_team_manager)
        self.assertFalse(self.holding.is_team_manager)
        self.assertEqual(
            TeamRoleAssignment.objects.filter(
                team=self.team_a, is_team_manager=True
            ).count(),
            1,
        )

    def test_hr_can_clear_and_set_a_manager(self):
        cleared = clear_team_manager(assignment=self.holding, actor=self.hr)
        self.assertFalse(cleared.is_team_manager)
        again = set_team_manager(assignment=self.holding, actor=self.hr)
        self.assertTrue(again.is_team_manager)

    def test_manager_cannot_designate_a_manager(self):
        # Reaching the set-manager action is HR-only at the viewset, so a
        # manager is refused there.
        self._as_manager()
        url = f"{TEAM_ROLE_ASSIGNMENTS_URL}{self.holding.pk}/set-manager/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
