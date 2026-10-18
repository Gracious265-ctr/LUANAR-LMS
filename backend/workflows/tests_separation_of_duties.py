"""Separation of duties: HR owns the org's shape, a team manager owns one team.

The split the product promises is deliberately narrow. HR creates teams, names
their category and campus, moves them in and out of force, and designates the
single manager; the manager then runs *their* team day to day — members, chains,
steps, and the normal-member pool — and reaches nothing else. These tests pin
both halves at the endpoints:

* a manager's own team is editable, and its workflow configuration, membership,
  and approver appointments are all reachable;
* every one of those writes on *another* team is refused — most as a 404 because
  the team is scoped out of the manager's queryset, so the manager cannot even
  learn whether a foreign team or chain exists;
* creating a team, designating/clearing a manager, and writing team-wide role
  assignments stay HR-only;
* the member-candidate list a manager's picker reads is scoped to exactly who
  the write would accept — unassigned, category-matched, non-wide — and is
  readable only for the manager's own team.

The service layer is asserted alongside the endpoint in the places where a
future path could bypass the queryset, so the delegation cannot be widened by a
route that forgets the scope.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import EmployeeProfile

from organisation.services import (
    WorkflowMemberError,
    add_team_member,
    create_team_role_assignment,
)
from workflows.models import SectionMember, Workflow

from .testing import (
    DEV_PASSWORD,
    ensure_roles,
    grant_approver_role,
    make_employee,
    make_team,
)

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"
SECTION_MEMBERS_URL = "/api/v1/section-members/"
TEAM_ROLE_ASSIGNMENTS_URL = "/api/v1/team-role-assignments/"


class SeparationOfDutiesTests(TestCase):
    """HR keeps the org; a manager gets their team and nothing wider."""

    def setUp(self):
        self.client = APIClient()
        self.hr = User.objects.create_user(
            username="hr@sod.test",
            email="hr@sod.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        self.team_a = make_team("Registry Team", ("supervisor",))
        self.team_b = make_team("Bursar Team", ("supervisor",))

        self.manager = make_employee("manager@sod.test", team=None)
        self.member = make_employee("member@sod.test", team=None)
        self.outsider = make_employee("outsider@sod.test", team=None)

        role = ensure_roles("hod")["hod"]
        self.holding = create_team_role_assignment(
            team=self.team_a,
            role=role,
            user=self.manager,
            actor=self.hr,
            is_team_manager=True,
        )

    def _as_manager(self):
        self.client.force_authenticate(self.manager)

    def _as(self, user):
        self.client.force_authenticate(user)

    # --- workflow configuration -------------------------------------------

    def test_manager_edits_their_workflows_stages(self):
        self._as_manager()
        url = f"{WORKFLOWS_URL}{self.team_a.workflow_id}/"
        response = self.client.patch(
            url,
            {
                "sections": [
                    {"name": "Supervisor", "approver_role": "supervisor", "order": 1}
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        workflow = Workflow.objects.get(pk=self.team_a.workflow_id)
        self.assertEqual(
            list(workflow.sections.order_by("order").values_list("name", flat=True)),
            ["Supervisor"],
        )

    def test_manager_cannot_edit_another_teams_workflow(self):
        self._as_manager()
        url = f"{WORKFLOWS_URL}{self.team_b.workflow_id}/"
        response = self.client.patch(url, {"name": "Hijacked"}, format="json")
        # The chain is scoped out of the manager's queryset, so it 404s.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_cannot_read_another_teams_workflow(self):
        self._as_manager()
        response = self.client.get(f"{WORKFLOWS_URL}{self.team_b.workflow_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- team membership ---------------------------------------------------

    def test_manager_adds_and_removes_a_member_on_their_team(self):
        self._as_manager()
        add_url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        added = self.client.post(add_url, {"user": self.member.pk}, format="json")
        self.assertEqual(added.status_code, status.HTTP_201_CREATED, added.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.employee_profile.team_id, self.team_a.pk)

        remove_url = f"{TEAMS_URL}{self.team_a.pk}/members/{self.member.pk}/"
        removed = self.client.delete(remove_url)
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.employee_profile.team_id)

    def test_manager_cannot_add_a_member_to_another_team_at_the_service(self):
        # Bypassing the endpoint's queryset scoping still refuses: the service
        # checks the actor against the team it is handed.
        with self.assertRaises(WorkflowMemberError):
            add_team_member(team=self.team_b, user=self.member, actor=self.manager)

    def test_hr_cannot_add_or_remove_members(self):
        # Membership follows the handover: once HR has created the team and
        # designated its manager, the roster is the manager's to run.
        self._as(self.hr)
        add_url = f"{TEAMS_URL}{self.team_a.pk}/members/"
        added = self.client.post(add_url, {"user": self.member.pk}, format="json")
        self.assertEqual(added.status_code, status.HTTP_403_FORBIDDEN)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.employee_profile.team_id)

        self._as_manager()
        appointed = self.client.post(add_url, {"user": self.member.pk}, format="json")
        self.assertEqual(appointed.status_code, status.HTTP_201_CREATED, appointed.data)

        self._as(self.hr)
        removed = self.client.delete(
            f"{TEAMS_URL}{self.team_a.pk}/members/{self.member.pk}/"
        )
        self.assertEqual(removed.status_code, status.HTTP_403_FORBIDDEN)

    # --- workflow membership (the normal-member pool) ----------------------

    def test_manager_assigns_a_normal_member_to_their_workflow(self):
        add_team_member(team=self.team_a, user=self.member, actor=self.hr)
        self._as_manager()
        url = f"{WORKFLOWS_URL}{self.team_a.workflow_id}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_manager_cannot_assign_a_member_to_another_teams_workflow(self):
        add_team_member(team=self.team_b, user=self.member, actor=self.hr)
        self._as_manager()
        url = f"{WORKFLOWS_URL}{self.team_b.workflow_id}/members/"
        response = self.client.post(url, {"user": self.member.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- section approvers -------------------------------------------------

    def _section(self, team):
        return team.workflow.sections.order_by("order").first()

    def test_manager_appoints_an_approver_on_their_team(self):
        add_team_member(team=self.team_a, user=self.member, actor=self.hr)
        self._as_manager()
        response = self.client.post(
            SECTION_MEMBERS_URL,
            {"section": self._section(self.team_a).pk, "user": self.member.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_manager_cannot_appoint_an_approver_on_another_team(self):
        add_team_member(team=self.team_b, user=self.member, actor=self.hr)
        self._as_manager()
        section = self._section(self.team_b)
        response = self.client.post(
            SECTION_MEMBERS_URL,
            {"section": section.pk, "user": self.member.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertFalse(
            SectionMember.objects.filter(section=section, user=self.member).exists()
        )

    # --- team identity and lifecycle stay with HR --------------------------

    def test_manager_cannot_create_a_team(self):
        self._as_manager()
        response = self.client.post(
            TEAMS_URL,
            {"name": "Shadow Team", "code": "shadow-team", "category": "administration"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_edit_a_teams_identity(self):
        # Editing a team's details is HR-only whatever the team, so the
        # permission check refuses before the queryset is consulted.
        self._as_manager()
        response = self.client.patch(
            f"{TEAMS_URL}{self.team_b.pk}/", {"description": "no"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_write_team_role_assignments(self):
        self._as_manager()
        response = self.client.post(
            TEAM_ROLE_ASSIGNMENTS_URL,
            {"team": self.team_a.pk, "role": ensure_roles("hod")["hod"].pk, "user": self.member.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_clear_their_own_designation(self):
        self._as_manager()
        response = self.client.post(
            f"{TEAM_ROLE_ASSIGNMENTS_URL}{self.holding.pk}/clear-manager/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- scoping of the reads a manager is allowed -------------------------

    def test_manager_team_list_holds_only_their_team(self):
        self._as_manager()
        response = self.client.get(TEAMS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual([row["id"] for row in rows], [self.team_a.pk])

    def test_manager_cannot_read_another_team(self):
        self._as_manager()
        response = self.client.get(f"{TEAMS_URL}{self.team_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- member candidates -------------------------------------------------

    def test_member_candidates_offer_exactly_who_the_write_accepts(self):
        candidate = make_employee("candidate@sod.test", team=None)
        wrong_category = make_employee(
            "academic@sod.test",
            team=None,
            category=EmployeeProfile.Category.ACADEMIC,
        )
        other_team_member = make_employee("other-team@sod.test", team=self.team_b)
        wide = make_employee("wide@sod.test", team=None)
        grant_approver_role(wide, "registrar")

        self._as_manager()
        response = self.client.get(
            f"{TEAMS_URL}{self.team_a.pk}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        offered = {row["id"] for row in response.data}

        self.assertIn(candidate.pk, offered)
        # The manager themself is a wide approver (a team-wide holding), so the
        # picker must not offer them as a normal member.
        self.assertNotIn(self.manager.pk, offered)
        self.assertNotIn(wrong_category.pk, offered)
        self.assertNotIn(other_team_member.pk, offered)
        self.assertNotIn(wide.pk, offered)
        # The response carries what the roster row needs and no team, because
        # every candidate is by definition unassigned.
        row = next(row for row in response.data if row["id"] == candidate.pk)
        self.assertEqual(
            set(row), {"id", "full_name", "email", "designation"}
        )

    def test_member_candidates_are_scoped_to_the_managers_own_team(self):
        self._as_manager()
        response = self.client.get(
            f"{TEAMS_URL}{self.team_b.pk}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_candidates_refuse_a_non_manager(self):
        self._as(self.outsider)
        response = self.client.get(
            f"{TEAMS_URL}{self.team_a.pk}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
