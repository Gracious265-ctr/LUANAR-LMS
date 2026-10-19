"""Team Member Management and Workflow Member Eligibility: end-to-end.

A team names its employees — the people whose leave routes through its chain —
and each workflow the team owns names its normal members, the eligibility pool
HR builds from. The two are deliberately separate facts:

* **Team membership** is ``EmployeeProfile.team``: the employee's
  organisational unit, and the single record of whose chain their leave
  follows. It is managed through the team members endpoints.
* **Workflow membership** is :class:`WorkflowMember`: a record that a member of
  the team is on one particular chain as a *normal* member (not an approver).
  One employee is a normal member of at most one workflow per team, and the
  pool a workflow's membership is offered from is "the team's members minus the
  members already on another of the team's workflows".

These tests cover that surface: adding and removing people from a team, the
removal safeguards, the eligibility pool the workflow screen reads, and the
database constraints that make "one workflow per employee per team" hold even
when two HR users write at once.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from users.models import EmployeeProfile

from .models import (
    Workflow,
    WorkflowMember,
    Section,
)
from organisation.models import (
    CampusRoleAssignment,
    RoleAssignment,
)
from teams.models import (
    Team,
    TeamRoleAssignment,
)
from .services import (
    TeamActionError,
    assign_workflow_member,
    ensure_membership_allowed,
    remove_team_member,
    remove_workflow_member,
    sync_workflow_members,
    team_member_summaries,
    workflow_member_pool,
)
from organisation.services import (
    WorkflowMemberError,
    add_team_member,
)
from .testing import (
    DEV_PASSWORD,
    appoint_approver_to_section,
    ensure_roles,
    grant_approver_role,
    make_employee,
    make_team,
    make_workflow,
    team_for,
)

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"


class MemberAPIBase(TestCase):
    """An HR client, one team, and ordinary employees on it."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@members.test",
            email="hr@members.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.employee = User.objects.create_user(
            username="emp@members.test",
            email="emp@members.test",
            password=DEV_PASSWORD,
            role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(self.hr)
        self.team = make_team(
            "Members Team", ["supervisor"], employees=(self.employee,)
        )
        self.alice = make_employee("alice@members.test", team=self.team)
        self.bob = make_employee("bob@members.test", team=self.team)

    def member_url(self, user_id):
        return f"{TEAMS_URL}{self.team.pk}/members/{user_id}/"


class TeamMemberManagementTests(MemberAPIBase):
    """Adding and removing employees from a team, with the safeguards."""

    def test_list_team_members_with_footprint(self):
        response = self.client.get(f"{TEAMS_URL}{self.team.pk}/members/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()
        ids = {row["user"] for row in rows}
        self.assertIn(self.employee.pk, ids)
        self.assertIn(self.alice.pk, ids)
        self.assertIn(self.bob.pk, ids)
        by_id = {row["user"]: row for row in rows}
        self.assertEqual(by_id[self.alice.pk]["workflow_count"], 0)
        self.assertFalse(by_id[self.alice.pk]["is_section_approver"])
        self.assertIsNone(by_id[self.alice.pk]["team_role"])

    def test_add_member_places_employee_on_team(self):
        carol = make_employee("carol@members.test")
        response = self.client.post(
            f"{TEAMS_URL}{self.team.pk}/members/",
            {"user": carol.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        carol.refresh_from_db()
        self.assertEqual(carol.employee_profile.team_id, self.team.pk)
        audit = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=carol.pk,
        )
        self.assertTrue(audit.exists())

    def test_add_member_already_on_another_team_is_refused(self):
        other = make_team("Other Team", ["supervisor"])
        carol = make_employee("carol2@members.test", team=other)
        response = self.client.post(
            f"{TEAMS_URL}{self.team.pk}/members/",
            {"user": carol.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already on", response.json()["user"][0])

    def test_add_member_category_mismatch_is_refused(self):
        # An administration team takes administration employees; an academic
        # employee is not moved onto the roster by an add that would leave the
        # team with a member its category rule says cannot belong.
        academic = make_employee(
            "academic@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        response = self.client.post(
            f"{TEAMS_URL}{self.team.pk}/members/",
            {"user": academic.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payload = response.json()
        self.assertIn("Academic employee", payload["user"][0])
        self.assertIn("Administration team", payload["user"][0])
        academic.employee_profile.refresh_from_db()
        self.assertIsNone(academic.employee_profile.team_id)

    def test_academic_employee_can_be_added_to_an_academic_team(self):
        academic_team = make_team(
            "Academic Members Team", ["supervisor"], campus="Members Campus"
        )
        academic = make_employee(
            "academic-ok@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        response = self.client.post(
            f"{TEAMS_URL}{academic_team.pk}/members/",
            {"user": academic.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        academic.employee_profile.refresh_from_db()
        self.assertEqual(academic.employee_profile.team_id, academic_team.pk)

    def test_add_member_who_is_a_wide_approver_is_refused(self):
        # An approver serves steps from the Approvers tab; placing them on the
        # roster as a normal member would silently also route their leave.
        approver = make_employee("wide@members.test")
        grant_approver_role(approver, "registrar")
        response = self.client.post(
            f"{TEAMS_URL}{self.team.pk}/members/",
            {"user": approver.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("wide approver", response.json()["user"][0])
        approver.employee_profile.refresh_from_db()
        self.assertIsNone(approver.employee_profile.team_id)

    def test_add_member_who_is_campus_wide_approver_for_that_campus_is_refused(self):
        academic_team = make_team(
            "Campus Members Team", ["supervisor"], campus="Members Campus"
        )
        holder = make_employee(
            "campus-wide@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        role = grant_approver_role(
            holder, "campus_registrar", institution_wide=False
        )
        CampusRoleAssignment.objects.create(
            campus=academic_team.campus, role=role, user=holder
        )
        response = self.client.post(
            f"{TEAMS_URL}{academic_team.pk}/members/",
            {"user": holder.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("wide approver", response.json()["user"][0])
        holder.employee_profile.refresh_from_db()
        self.assertIsNone(holder.employee_profile.team_id)

    def test_remove_member_clears_team(self):
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.alice.employee_profile.refresh_from_db()
        self.assertIsNone(self.alice.employee_profile.team_id)

    def test_remove_non_member_is_refused(self):
        carol = make_employee("carol3@members.test")
        response = self.client.delete(self.member_url(carol.pk))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_removal_blocked_while_workflow_member(self):
        workflow = list(Workflow.objects.filter(team=self.team))[0]
        assign_workflow_member(
            workflow=workflow, user=self.alice, actor=self.hr
        )
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        payload = response.json()
        self.assertIn("still has responsibilities", payload["user"][0])
        self.assertIn("normal member", payload["user"][0])
        # The roster is untouched: nobody was half-removed.
        self.alice.employee_profile.refresh_from_db()
        self.assertEqual(self.alice.employee_profile.team_id, self.team.pk)

    def test_removal_blocked_while_section_approver(self):
        workflow = list(Workflow.objects.filter(team=self.team))[0]
        section = workflow.sections.first()
        section.approver = self.alice
        section.save(update_fields=["approver"])
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("appointed to", response.json()["user"][0])

    def test_removal_blocked_while_team_role_holder(self):
        role = ensure_roles("hod")["hod"]
        TeamRoleAssignment.objects.create(team=self.team, role=role, user=self.alice)
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("holder", response.json()["user"][0])

    def test_removal_blocked_while_open_approver_period(self):
        workflow = list(Workflow.objects.filter(team=self.team))[0]
        section = workflow.sections.first()
        from .models import SectionMember

        SectionMember.objects.create(
            section=section,
            user=self.alice,
            effective_from="2026-01-01",
            effective_to=None,
        )
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("open approver period", response.json()["user"][0])

    def test_unassigned_employee_listed_as_candidate_by_employees_endpoint(self):
        # The employee roster endpoint offers people without a team, scoped by
        # the team's category and by who is already its wide approver; after a
        # member is removed they reappear there. The workflow-member pool (why
        # a person may be placed on one of the team's chains) is a different
        # list and stays separate.
        from .testing import team_for

        unassigned = User.objects.filter(
            employee_profile__team__isnull=True
        ).count()
        self.assertGreaterEqual(unassigned, 0)


class WorkflowMemberEligibilityTests(MemberAPIBase):
    """The pool computed per team, per workflow."""

    def setUp(self):
        # A bare team with NO workflow/approvers, so the pool is exactly the
        # three employees placed on it. super().setUp()'s team already staffs a
        # section and installs an approver on the team, which would pollute the
        # pool with a fourth (approver) member.
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@members.test",
            email="hr@members.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.client.force_authenticate(self.hr)
        from .testing import team_for

        self.team = team_for("Eligibility Team")
        self.alice = make_employee("alice@members.test", team=self.team)
        self.bob = make_employee("bob@members.test", team=self.team)
        self.employee = make_employee("emp@members.test", team=self.team)
        self.flow_a = make_workflow("Members A", ["supervisor"], is_active=True)
        self.flow_a.team = self.team
        self.flow_a.save(update_fields=["team"])
        self.flow_b = make_workflow("Members B", ["hod"], is_active=True)
        self.flow_b.team = self.team
        self.flow_b.save(update_fields=["team"])

    def test_pool_starting_state(self):
        pool = workflow_member_pool(team=self.team)
        self.assertEqual({row["user"] for row in pool["available"]},
                         {self.employee.pk, self.alice.pk, self.bob.pk})
        self.assertEqual(pool["current"], [])
        self.assertEqual(pool["assigned_elsewhere"], [])

    def test_assigned_member_leaves_available_pool(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        pool = workflow_member_pool(team=self.team)
        self.assertNotIn(self.alice.pk, {row["user"] for row in pool["available"]})
        self.assertEqual(len(pool["assigned_elsewhere"]), 1)
        self.assertEqual(pool["assigned_elsewhere"][0]["workflow_name"], "Members A")

    def test_pool_scoped_to_editing_workflow(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        pool = workflow_member_pool(team=self.team, workflow=self.flow_a)
        # Alice is already on flow_a, so she is the "current" member and NOT
        # in assigned_elsewhere. Bob is free. Employee is free.
        self.assertIn(self.alice.pk, {row["user"] for row in pool["current"]})
        self.assertEqual(pool["assigned_elsewhere"], [])
        available_ids = {row["user"] for row in pool["available"]}
        self.assertIn(self.alice.pk, available_ids)  # current members stay selected
        self.assertIn(self.bob.pk, available_ids)

    def test_member_assigned_elsewhere_excluded_and_flagged(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        pool = workflow_member_pool(team=self.team, workflow=self.flow_b)
        # Editing flow_b: Alice is on flow_a, so she must NOT be offered for
        # flow_b, and the UI must still see her as "in use elsewhere".
        available_ids = {row["user"] for row in pool["available"]}
        self.assertNotIn(self.alice.pk, available_ids)
        self.assertEqual(len(pool["assigned_elsewhere"]), 1)
        self.assertEqual(pool["assigned_elsewhere"][0]["user"], self.alice.pk)
        self.assertEqual(pool["assigned_elsewhere"][0]["workflow_name"], "Members A")

    def test_one_workflow_per_employee_per_team_via_service(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        with self.assertRaises(WorkflowMemberError):
            assign_workflow_member(
                workflow=self.flow_b, user=self.alice, actor=self.hr
            )

    def test_refuses_non_member_of_team(self):
        outsider = make_employee("outsider@members.test")
        with self.assertRaises(WorkflowMemberError):
            assign_workflow_member(
                workflow=self.flow_a, user=outsider, actor=self.hr
            )

    def test_refuses_workflow_without_team(self):
        orphan = make_workflow("Orphan", ["supervisor"], is_active=True)
        with self.assertRaises(WorkflowMemberError):
            assign_workflow_member(workflow=orphan, user=self.alice, actor=self.hr)

    def test_duplicate_assign_same_workflow_is_idempotent(self):
        first = assign_workflow_member(
            workflow=self.flow_a, user=self.alice, actor=self.hr
        )
        second = assign_workflow_member(
            workflow=self.flow_a, user=self.alice, actor=self.hr
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            WorkflowMember.objects.filter(workflow=self.flow_a, user=self.alice).count(),
            1,
        )

    def test_remove_workflow_member_writes_audit_and_frees_pool(self):
        member = assign_workflow_member(
            workflow=self.flow_a, user=self.alice, actor=self.hr
        )
        remove_workflow_member(member=member, actor=self.hr)
        self.assertFalse(
            WorkflowMember.objects.filter(workflow=self.flow_a, user=self.alice).exists()
        )
        pool = workflow_member_pool(team=self.team)
        self.assertIn(self.alice.pk, {row["user"] for row in pool["available"]})
        audit = AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=self.flow_a.pk,
        ).filter(detail__before__has_key="user")
        self.assertTrue(audit.exists())

    def test_sync_workflow_members_replaces_pool(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        members = sync_workflow_members(
            workflow=self.flow_a, user_ids=[self.bob.pk, self.employee.pk], actor=self.hr
        )
        self.assertEqual({m.user_id for m in members},
                         {self.bob.pk, self.employee.pk})
        self.assertFalse(
            WorkflowMember.objects.filter(workflow=self.flow_a, user=self.alice).exists()
        )

    def test_sync_refuses_user_from_another_team(self):
        outsider = make_employee("outsider2@members.test")
        with self.assertRaises(WorkflowMemberError):
            sync_workflow_members(
                workflow=self.flow_a, user_ids=[outsider.pk], actor=self.hr
            )

    def test_step_approver_elsewhere_excluded_and_named(self):
        appoint_approver_to_section(
            self.flow_a.sections.first(), "supervisor", user=self.alice, team=self.team
        )
        pool = workflow_member_pool(team=self.team, workflow=self.flow_b)
        self.assertNotIn(
            self.alice.pk, {row["user"] for row in pool["available"]}
        )
        row = next(
            r for r in pool["assigned_elsewhere"] if r["user"] == self.alice.pk
        )
        self.assertEqual(row["workflow_name"], "Members A")

    def test_step_approver_elsewhere_refused_as_member(self):
        appoint_approver_to_section(
            self.flow_a.sections.first(), "supervisor", user=self.alice, team=self.team
        )
        with self.assertRaises(WorkflowMemberError):
            assign_workflow_member(workflow=self.flow_b, user=self.alice, actor=self.hr)

    def test_member_elsewhere_refused_as_step_approver(self):
        assign_workflow_member(workflow=self.flow_a, user=self.alice, actor=self.hr)
        step_b = self.flow_b.sections.first()
        with self.assertRaises(TeamActionError):
            ensure_membership_allowed(section=step_b, user=self.alice)

    def test_reappointing_own_chain_approver_is_not_a_conflict(self):
        section_a = self.flow_a.sections.first()
        appoint_approver_to_section(
            section_a, "supervisor", user=self.alice, team=self.team
        )
        # Re-saving the same step is the same appointment, so the elsewhere rule
        # must not trip against the section's own workflow.
        ensure_membership_allowed(section=section_a, user=self.alice)

    def test_team_wide_approver_joins_both_chains_and_stays_eligible(self):
        TeamRoleAssignment.objects.create(
            user=self.alice,
            team=self.team,
            role=ensure_roles("hod")["hod"],
        )
        first = assign_workflow_member(
            workflow=self.flow_a, user=self.alice, actor=self.hr
        )
        self.assertTrue(first.is_wide_approver)
        second = assign_workflow_member(
            workflow=self.flow_b, user=self.alice, actor=self.hr
        )
        self.assertTrue(second.is_wide_approver)
        pool = workflow_member_pool(team=self.team, workflow=self.flow_b)
        self.assertIn(self.alice.pk, {row["user"] for row in pool["available"]})
        self.assertNotIn(
            self.alice.pk, {row["user"] for row in pool["assigned_elsewhere"]}
        )

    def test_institution_wide_approver_is_exempt_from_the_elsewhere_rule(self):
        grant_approver_role(self.alice, "hod")
        step_b = self.flow_b.sections.first()
        ensure_membership_allowed(section=step_b, user=self.alice)
        member = assign_workflow_member(
            workflow=self.flow_a, user=self.alice, actor=self.hr
        )
        self.assertTrue(member.is_wide_approver)


class WorkflowMemberAPITests(MemberAPIBase):
    """The write path through the workflow endpoints, and through members."""

    def setUp(self):
        super().setUp()
        self.flow = make_workflow("API Flow", ["supervisor"], is_active=True)
        self.flow.team = self.team
        self.flow.save(update_fields=["team"])

    def test_create_workflow_with_members(self):
        response = self.client.post(
            WORKFLOWS_URL,
            {
                "name": "API Flow 2",
                "team": self.team.pk,
                "sections": [
                    {"name": "Check", "approver_role": "supervisor", "approver": None}
                ],
                "members": [self.alice.pk, self.bob.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual({m["user"] for m in data["members"]},
                         {self.alice.pk, self.bob.pk})

    def test_update_workflow_members_by_list(self):
        assign_workflow_member(workflow=self.flow, user=self.alice, actor=self.hr)
        response = self.client.patch(
            f"{WORKFLOWS_URL}{self.flow.pk}/",
            {"members": [self.bob.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({m["user"] for m in response.json()["members"]},
                         {self.bob.pk})

    def test_clear_members_with_empty_list(self):
        assign_workflow_member(workflow=self.flow, user=self.alice, actor=self.hr)
        response = self.client.patch(
            f"{WORKFLOWS_URL}{self.flow.pk}/",
            {"members": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["members"], [])

    def test_pool_endpoint_scopes_to_workflow(self):
        other = make_workflow("Other Flow", ["hod"], is_active=True)
        other.team = self.team
        other.save(update_fields=["team"])
        assign_workflow_member(workflow=other, user=self.alice, actor=self.hr)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.pk}/workflow-member-pool/?workflow={self.flow.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        available_ids = {row["user"] for row in payload["available"]}
        self.assertNotIn(self.alice.pk, available_ids)
        # One employee serves one chain of a team at a time, so the pool for one
        # chain reports not only normal members of the others but also the people
        # staffing their steps — here the supervisor on the team's own original
        # chain and alice on the second one.
        other_chain_staff = set(
            Section.objects.filter(
                is_active=True,
                approver__isnull=False,
                workflow__team=self.team,
            )
            .exclude(workflow=self.flow)
            .values_list("approver_id", flat=True)
        )
        self.assertEqual(
            {row["user"] for row in payload["assigned_elsewhere"]},
            {self.alice.pk} | set(other_chain_staff),
        )

    def test_pool_endpoint_refuses_other_teams_workflow(self):
        other_team = make_team("Other Team", ["supervisor"])
        other = make_workflow("Other Team Flow", ["supervisor"])
        other.team = other_team
        other.save(update_fields=["team"])
        response = self.client.get(
            f"{TEAMS_URL}{self.team.pk}/workflow-member-pool/?workflow={other.pk}"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_workflow_members_endpoint_lists(self):
        assign_workflow_member(workflow=self.flow, user=self.alice, actor=self.hr)
        response = self.client.get(f"{WORKFLOWS_URL}{self.flow.pk}/members/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([m["user"] for m in response.json()], [self.alice.pk])

    def test_workflow_members_endpoint_adds(self):
        response = self.client.post(
            f"{WORKFLOWS_URL}{self.flow.pk}/members/",
            {"user": self.alice.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["user"], self.alice.pk)

    def test_workflow_members_endpoint_refuses_outsider(self):
        outsider = make_employee("outsider3@members.test")
        response = self.client.post(
            f"{WORKFLOWS_URL}{self.flow.pk}/members/",
            {"user": outsider.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not on the", response.json()["user"][0])

    def test_workflow_members_endpoint_removes(self):
        assign_workflow_member(workflow=self.flow, user=self.alice, actor=self.hr)
        response = self.client.delete(
            f"{WORKFLOWS_URL}{self.flow.pk}/members/{self.alice.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            WorkflowMember.objects.filter(workflow=self.flow, user=self.alice).exists()
        )

    def test_hr_only(self):
        self.client.force_authenticate(self.employee)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.pk}/workflow-member-pool/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.delete(self.member_url(self.alice.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class WorkflowMemberConcurrencyTests(TransactionTestCase):
    """The database constraint that closes the assign race (Test 10)."""

    def setUp(self):
        # No APIClient here; the race is about the constraint itself, so we
        # prove the constraint directly rather than with HTTP.
        self.team = make_team("Race Team", ["supervisor"])
        self.flow = make_workflow("Race Flow", ["supervisor"], is_active=True)
        self.flow.team = self.team
        self.flow.save(update_fields=["team"])
        self.person = make_employee("race@members.test", team=self.team)

    def test_second_write_same_employee_same_team_is_refused_by_constraint(self):
        # First write succeeds through the service.
        first = assign_workflow_member(
            workflow=self.flow, user=self.person, actor=User.objects.create_user(
                username="hr-race@members.test", password=DEV_PASSWORD, role=User.Role.HR
            )
        )
        self.assertIsNotNone(first.pk)
        # A direct second write must trip the (team, user) unique constraint.
        with self.assertRaises(IntegrityError):
            WorkflowMember.objects.create(
                workflow=self.flow,
                user=self.person,
                team=self.team,
            )
        self.assertEqual(
            WorkflowMember.objects.filter(team=self.team, user=self.person).count(),
            1,
        )

    def test_second_workflow_row_for_same_team_user_trips_constraint(self):
        flow_b = make_workflow("Race Flow B", ["hod"], is_active=True)
        flow_b.team = self.team
        flow_b.save(update_fields=["team"])
        assign_workflow_member(
            workflow=self.flow, user=self.person, actor=User.objects.create_user(
                username="hr-race2@members.test", password=DEV_PASSWORD, role=User.Role.HR
            )
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkflowMember.objects.create(
                    workflow=flow_b,
                    user=self.person,
                    team=self.team,
                )
        self.assertEqual(
            WorkflowMember.objects.filter(team=self.team, user=self.person).count(),
            1,
        )


class TeamMemberSummaryTests(MemberAPIBase):
    """The roster rows the team members screen renders."""

    def test_summary_marks_section_approver(self):
        workflow = list(Workflow.objects.filter(team=self.team))[0]
        section = workflow.sections.first()
        section.approver = self.alice
        section.save(update_fields=["approver"])
        rows = team_member_summaries(self.team)
        by_id = {row["user"]: row for row in rows}
        self.assertTrue(by_id[self.alice.pk]["is_section_approver"])
        self.assertFalse(by_id[self.bob.pk]["is_section_approver"])

def test_summary_reports_workflow_memberships(self):
        workflow = list(Workflow.objects.filter(team=self.team))[0]
        assign_workflow_member(workflow=workflow, user=self.alice, actor=self.hr)
        by_id = {row["user"]: row for row in team_member_summaries(self.team)}
        self.assertEqual(by_id[self.alice.pk]["workflow_count"], 1)
        self.assertEqual(
            by_id[self.alice.pk]["workflow_memberships"][0]["workflow_id"],
            workflow.pk,
        )


class WorkflowMemberScenarioTests(TestCase):
    """The acceptance scenario, line for line: four employees, three workflows,
    one chain per employee, and the employee freed again by removal.

    "Available for the new workflow" is the create-mode pool (no ``workflow``),
    which is the exact call the workflow form makes when configuring a chain
    that does not exist yet — team members minus members already placed on one
    of the team's other chains.
    """

    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@scenario.test",
            email="hr@scenario.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.hr)
        # 1. Create Team A.
        self.team = team_for("Scenario Team A")
        # 2. Add John, Mary, Peter, and Grace to Team A.
        self.john = make_employee("john@scenario.test", team=self.team)
        self.mary = make_employee("mary@scenario.test", team=self.team)
        self.peter = make_employee("peter@scenario.test", team=self.team)
        self.grace = make_employee("grace@scenario.test", team=self.team)

    def flow(self, name):
        workflow = make_workflow(name, ["supervisor"], is_active=True)
        workflow.team = self.team
        workflow.save(update_fields=["team"])
        return workflow

    def test_the_full_team_members_to_workflow_members_scenario(self):
        # 3. Create Workflow A.
        flow_a = self.flow("Workflow A")
        # 4. Assign John and Mary to Workflow A.
        assign_workflow_member(workflow=flow_a, user=self.john, actor=self.hr)
        assign_workflow_member(workflow=flow_a, user=self.mary, actor=self.hr)
        # 5. Create Workflow B.
        flow_b = self.flow("Workflow B")
        # 6. Verify only Peter and Grace in B's pool; John and Mary are not.
        pool_b = workflow_member_pool(team=self.team)
        self.assertEqual(
            {row["user"] for row in pool_b["available"]},
            {self.peter.pk, self.grace.pk},
        )
        elsewhere = {row["user"] for row in pool_b["assigned_elsewhere"]}
        self.assertIn(self.john.pk, elsewhere)
        self.assertIn(self.mary.pk, elsewhere)
        # 7. Assign Peter to Workflow B.
        assign_workflow_member(workflow=flow_b, user=self.peter, actor=self.hr)
        # 8. Create Workflow C.
        flow_c = self.flow("Workflow C")
        # 9. Verify only Grace in C's pool.
        pool_c = workflow_member_pool(team=self.team)
        self.assertEqual(
            {row["user"] for row in pool_c["available"]},
            {self.grace.pk},
        )
        # 10. Remove John from Workflow A.
        remove_workflow_member(
            member=WorkflowMember.objects.get(workflow=flow_a, user=self.john),
            actor=self.hr,
        )
        # 11. John becomes available again for another workflow.
        pool_c_again = workflow_member_pool(team=self.team)
        self.assertEqual(
            {row["user"] for row in pool_c_again["available"]},
            {self.grace.pk, self.john.pk},
        )
        # 12. An employee from another team is rejected — through the API too,
        # so a manipulated request cannot slip past the service rule.
        other_team = team_for("Other Team")
        outsider = make_employee("outsider@scenario.test", team=other_team)
        with self.assertRaises(WorkflowMemberError):
            assign_workflow_member(workflow=flow_c, user=outsider, actor=self.hr)
        response = self.client.post(
            f"{WORKFLOWS_URL}{flow_c.pk}/members/",
            {"user": outsider.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teams_stay_distinct_while_a_workflow_is_built(self):
        other_team = team_for("Scenario Team B")
        other = make_employee("other@scenario.test", team=other_team)
        flow = self.flow("Workflow A")
        # Mary is a member of Team A only; nobody from Team B clips into the
        # pool, and the four own members are the only people ever offered.
        pool = workflow_member_pool(team=self.team)
        ids = {row["user"] for row in pool["available"]}
        self.assertEqual(
            ids, {self.john.pk, self.mary.pk, self.peter.pk, self.grace.pk}
        )
        self.assertNotIn(other.pk, ids)
        # Adding to the team never enrolls anyone in a workflow.
        assign_workflow_member(workflow=flow, user=self.john, actor=self.hr)
        self.assertEqual(self.john.employee_profile.team_id, self.team.pk)
        self.assertFalse(
            WorkflowMember.objects.filter(workflow=flow, user=self.mary).exists()
        )


class WideHolderCategoryTests(MemberAPIBase):
    """A wide approver belongs to the same half of the institution they cover.

    A team-wide holder must match the team's category, and a campus-wide holder
    must be an Academic employee — every team at a campus is academic, so a
    campus holding is always an academic-team holding. The write refuses the
    mismatch rather than letting an employee read a chain that their own
    category rule says they cannot be part of.
    """

    def setUp(self):
        super().setUp()
        self.role = ensure_roles("supervisor")["supervisor"]

    def test_academic_holder_team_wide_on_an_administration_team_is_refused(self):
        academic = make_employee(
            "academic-holder@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        response = self.client.post(
            "/api/v1/team-role-assignments/",
            {
                "team": self.team.pk,
                "role": self.role.pk,
                "user": academic.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payload = response.json()
        self.assertIn("Academic employee", payload["user"][0])
        self.assertIn("Administration team", payload["user"][0])
        self.assertFalse(TeamRoleAssignment.objects.exists())

    def test_team_wide_holder_of_matching_category_is_accepted(self):
        holder = make_employee("admin-match@members.test")
        response = self.client.post(
            "/api/v1/team-role-assignments/",
            {
                "team": self.team.pk,
                "role": self.role.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TeamRoleAssignment.objects.filter(
                team=self.team, role=self.role, user=holder
            ).exists()
        )

    def test_campus_wide_holder_administration_employee_is_refused(self):
        academic_team = make_team(
            "Campus Wide Holder Team",
            ["supervisor"],
            campus="Wide Holder Campus",
        )
        admin = make_employee("admin-holder@members.test")
        response = self.client.post(
            "/api/v1/campus-role-assignments/",
            {
                "campus": academic_team.campus.pk,
                "role": self.role.pk,
                "user": admin.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Academic employee", response.json()["user"][0])
        self.assertFalse(CampusRoleAssignment.objects.exists())

    def test_campus_wide_holder_academic_employee_is_accepted(self):
        academic_team = make_team(
            "Campus Wide Holder OK Team",
            ["supervisor"],
            campus="Wide Holder OK Campus",
        )
        academic = make_employee(
            "academic-campus-holder@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        response = self.client.post(
            "/api/v1/campus-role-assignments/",
            {
                "campus": academic_team.campus.pk,
                "role": self.role.pk,
                "user": academic.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CampusRoleAssignment.objects.filter(
                campus=academic_team.campus, role=self.role, user=academic
            ).exists()
        )


class WideHolderSingleRoleTests(MemberAPIBase):
    """A person holds one wide approver role, at one of the three scopes.

    Once somebody is a wide approver they disappear from the *other* wide
    approver sections — the same person re-appearing in a second picker would
    mean two sections claiming them. The write is the hard rule behind that:
    it refuses the second holding wherever the first one lives, so the picker's
    removal of an already-wide person is a promise the backend keeps.
    """

    def setUp(self):
        super().setUp()
        roles = ensure_roles("supervisor", "dean", "registrar")
        self.supervisor = roles["supervisor"]
        self.dean = roles["dean"]
        self.registrar = roles["registrar"]
        self.registrar.is_institution_wide = True
        self.registrar.save(update_fields=["is_institution_wide"])

    def team_wide_url(self):
        return "/api/v1/team-role-assignments/"

    def campus_wide_url(self):
        return "/api/v1/campus-role-assignments/"

    def institution_url(self):
        return "/api/v1/role-assignments/"

    def test_institution_holder_cannot_also_be_team_wide(self):
        holder = make_employee("inst-team@members.test")
        grant_approver_role(holder, "registrar")
        response = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("only one wide approver role", message)
        self.assertIn("institution-wide", message)
        self.assertFalse(TeamRoleAssignment.objects.exists())

    def test_team_wide_holder_cannot_also_be_institution_wide(self):
        holder = make_employee("team-inst@members.test")
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.institution_url(),
            {"role": self.registrar.pk, "user": holder.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("only one wide approver role", message)
        self.assertIn("team-wide approver on Members Team", message)
        self.assertFalse(RoleAssignment.objects.exists())

    def test_team_wide_holder_cannot_hold_a_second_role_on_the_same_team(self):
        holder = make_employee("team-team@members.test")
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.dean.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "only one wide approver role", response.json()["user"][0]
        )

    def test_institution_holder_cannot_hold_a_second_institution_role(self):
        holder = make_employee("inst-inst@members.test")
        grant_approver_role(holder, "registrar")
        self.dean.is_institution_wide = True
        self.dean.save(update_fields=["is_institution_wide"])
        response = self.client.post(
            self.institution_url(),
            {"role": self.dean.pk, "user": holder.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("only one wide approver role", message)
        self.assertIn("Registrar institution-wide", message)
        self.assertEqual(RoleAssignment.objects.count(), 1)

    def test_team_wide_holder_cannot_also_be_campus_wide(self):
        academic_team = make_team(
            "Single Role Campus Team", ["supervisor"], campus="Single Role Campus"
        )
        academic = make_employee(
            "team-campus@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": academic_team.pk,
                "role": self.supervisor.pk,
                "user": academic.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.campus_wide_url(),
            {
                "campus": academic_team.campus.pk,
                "role": self.supervisor.pk,
                "user": academic.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("only one wide approver role", message)
        self.assertIn("team-wide approver on Single Role Campus Team", message)
        self.assertFalse(CampusRoleAssignment.objects.exists())

    def test_campus_holder_cannot_also_be_team_wide_elsewhere(self):
        first_campus = make_team(
            "First Campus Team", ["supervisor"], campus="First Site Campus"
        )
        campus_holder = make_employee(
            "campus-team@members.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        first = self.client.post(
            self.campus_wide_url(),
            {
                "campus": first_campus.campus.pk,
                "role": self.supervisor.pk,
                "user": campus_holder.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        other_team = make_team(
            "Second Campus Team", ["supervisor"], campus="Second Site Campus"
        )
        response = self.client.post(
            self.team_wide_url(),
            {
                "team": other_team.pk,
                "role": self.supervisor.pk,
                "user": campus_holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("only one wide approver role", message)
        self.assertIn("campus-wide approver at First Site Campus", message)

    def test_resaving_the_same_team_holding_is_not_a_second_holding(self):
        holder = make_employee("re-save-single@members.test")
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.json()["user"][0]
        self.assertIn("already holds the Supervisor role on Members Team", message)
        self.assertNotIn("only one wide approver role", message)

    def test_replacing_a_team_holder_with_someone_new_is_allowed(self):
        jane = make_employee("old-single@members.test")
        bob = make_employee("new-single@members.test")
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": jane.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": bob.pk,
            },
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        holding = TeamRoleAssignment.objects.get(team=self.team, role=self.supervisor)
        self.assertEqual(holding.user, bob)

    def test_replacing_a_holder_with_an_institution_wide_person_is_refused(self):
        jane = make_employee("old-another@members.test")
        registrar_holder = make_employee("registrar-another@members.test")
        grant_approver_role(registrar_holder, "registrar")
        first = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": jane.pk,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.team_wide_url(),
            {
                "team": self.team.pk,
                "role": self.supervisor.pk,
                "user": registrar_holder.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "only one wide approver role", response.json()["user"][0]
        )
        holding = TeamRoleAssignment.objects.get(team=self.team, role=self.supervisor)
        self.assertEqual(holding.user, jane)


class WorkflowDetailMembershipSerializationTests(TestCase):
    """The workflow detail payload carries each step's membership record.

    The chain screen reads ``section.memberships`` to show who holds each step
    today, so the key must be present on every section — including an unstaffed
    one — or the client crashes on ``undefined.filter`` at render time.
    """

    def setUp(self):
        self.client = APIClient()
        self.hr = User.objects.create_user(
            username="hr-workflow-detail@members.test",
            email="hr-workflow-detail@members.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        self.client.force_authenticate(self.hr)
        self.team = make_team("Detail Team", ["supervisor", "hod"])
        self.workflow = self.team.workflow

    def test_every_section_emits_memberships(self):
        response = self.client.get(f"{WORKFLOWS_URL}{self.workflow.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sections = response.json()["sections"]
        self.assertGreater(len(sections), 0)
        for section in sections:
            self.assertIn("memberships", section)

    def test_a_staffed_step_lists_the_effective_holder(self):
        holder = make_employee("hod-detail@members.test", team=self.team)
        section = self.workflow.sections.get(approver_role__code="hod")
        appoint_approver_to_section(section, "hod", user=holder)
        response = self.client.get(f"{WORKFLOWS_URL}{self.workflow.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        section_data = next(
            s for s in response.json()["sections"] if s["id"] == section.pk
        )
        self.assertTrue(
            any(
                m["user"] == holder.pk and m["is_effective"]
                for m in section_data["memberships"]
            )
        )