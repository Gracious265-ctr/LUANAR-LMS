"""Tests for the On Leave read model and ``GET /api/v1/leave/on-leave/``.

The screen answers one question — "whose approved leave may I see, and when are
they away" — and the ladder that answers it is the backend's decision. These
tests pin each rung from the narrowest up, because the failure that matters is a
viewer seeing somebody whose leave is not theirs to read; a wider answer is
still a leak even when the row itself is unremarkable.

The chain rung is tested separately from the team rung on purpose: a team routes
several chains at once, so two colleagues on the same team can be on different
chains and must not see each other.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from campuses.models import CampusRoleAssignment
from chains.models import WorkflowMember
from chains.testing import (
    ensure_roles,
    make_employee,
    make_team,
    make_workflow,
)
from leave_types.models import LeaveType
from roles.models import RoleAssignment
from teams.models import TeamRoleAssignment
from users.models import EmployeeProfile

from ..models import LeaveApplication
from ..on_leave import (
    CAMPUS,
    CHAIN,
    INSTITUTION,
    ORGANISATION,
    SELF,
    TEAM,
    on_leave_payload,
    resolve_scope,
)

User = get_user_model()

URL = "/api/v1/leave/on-leave/"
TODAY = date(2026, 10, 26)


class OnLeaveTestBase(TestCase):
    """One approved application per person, and a leave type to name."""

    def setUp(self):
        self.roles = ensure_roles("supervisor", "hod", "registrar")
        self.annual = LeaveType.objects.create(name="Annual Leave", code="annual")

    def approved(self, user, *, start=None, end=None, leave_type=None,
                 status=LeaveApplication.Status.APPROVED):
        start = start or TODAY
        end = end or start
        return LeaveApplication.objects.create(
            employee=user,
            leave_type_id=(leave_type or self.annual).pk,
            start_date=start,
            end_date=end,
            working_days=max((end - start).days + 1, 1),
            status=status,
        )

    def payload(self, user, **kwargs):
        kwargs.setdefault("today", TODAY)
        return on_leave_payload(user=user, **kwargs)

    def employee_on(self, workflow, name, *, start=None, end=None, **kwargs):
        """A person on ``workflow``'s team with one approved application."""
        team = workflow.team
        user = make_employee(f"{name}@on-leave.test", team=team, **kwargs)
        application = self.approved(user, start=start, end=end)
        return user, application


class ScopeLadderTests(OnLeaveTestBase):
    """Each rung, narrowest first, and the one above it."""

    def test_an_employee_with_no_scope_sees_only_themselves(self):
        loner = make_employee("loner@on-leave.test")
        stranger = make_employee("stranger@on-leave.test")
        self.approved(loner)
        self.approved(stranger)

        payload = self.payload(loner)

        self.assertEqual(payload["scope"]["kind"], SELF)
        self.assertEqual(payload["results"][0]["employee"]["id"], loner.pk)

    def test_a_chain_member_sees_the_people_on_the_same_chain(self):
        team = make_team("Registry", ("supervisor", "hod"))
        workflow = team.workflow
        member, _ = self.employee_on(workflow, "chain-member")
        colleague, _ = self.employee_on(workflow, "chain-colleague")
        # Enrol both members on the workflow so they route through the same chain
        from chains.models import WorkflowMember
        WorkflowMember.objects.create(
            workflow=workflow,
            user=member,
            team=team,
            is_wide_approver=False,
        )
        WorkflowMember.objects.create(
            workflow=workflow,
            user=colleague,
            team=team,
            is_wide_approver=False,
        )
        outsider, _ = self.employee_on(
            make_team("Library", ("supervisor",)).workflow, "chain-outsider"
        )

        payload = self.payload(member)

        self.assertEqual(payload["scope"]["kind"], CHAIN)
        self.assertEqual(payload["scope"]["label"], team.workflow.name)
        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {member.pk, colleague.pk})
        self.assertNotIn(outsider.pk, ids)

    def test_a_chain_member_does_not_see_a_teammate_on_another_chain(self):
        team = make_team("Registry", ("supervisor", "hod"))
        second = make_workflow("Registry Senior Chain", ("supervisor", "registrar"))
        second.team = team
        second.save(update_fields=["team"])

        member, _ = self.employee_on(team.workflow, "default-chain")
        elsewhere, _ = self.employee_on(second, "other-chain")
        WorkflowMember.objects.create(
            workflow=second,
            user=elsewhere,
            team=team,
            is_wide_approver=False,
        )

        payload = self.payload(member)

        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {member.pk})
        self.assertNotIn(elsewhere.pk, ids)

    def test_a_team_manager_sees_the_whole_team_across_its_chains(self):
        team = make_team("Registry", ("supervisor", "hod"))
        second = make_workflow("Registry Senior Chain", ("supervisor", "registrar"))
        second.team = team
        second.save(update_fields=["team"])

        manager = make_employee("manager@on-leave.test", team=team)
        TeamRoleAssignment.objects.create(
            team=team,
            role=self.roles["supervisor"],
            user=manager,
            is_team_manager=True,
        )
        on_default, _ = self.employee_on(team.workflow, "managed-default")
        on_second, _ = self.employee_on(second, "managed-second")
        WorkflowMember.objects.create(
            workflow=second,
            user=on_second,
            team=team,
            is_wide_approver=False,
        )
        stranger, _ = self.employee_on(
            make_team("Library", ("supervisor",)).workflow, "unmanaged"
        )
        self.approved(manager)

        payload = self.payload(manager)

        self.assertEqual(payload["scope"]["kind"], TEAM)
        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {manager.pk, on_default.pk, on_second.pk})
        self.assertNotIn(stranger.pk, ids)

    def test_a_campus_approver_sees_their_campus_only(self):
        here = make_team("Campus A Faculty", ("supervisor",), campus="Campus A")
        elsewhere = make_team("Campus B Faculty", ("supervisor",), campus="Campus B")

        approver = make_employee("campus-approver@on-leave.test", team=here)
        CampusRoleAssignment.objects.create(
            campus=here.campus, role=self.roles["supervisor"], user=approver
        )
        self.approved(approver)
        colleague, _ = self.employee_on(here.workflow, "campus-a-colleague")
        other, _ = self.employee_on(elsewhere.workflow, "campus-b-colleague")

        payload = self.payload(approver)

        self.assertEqual(payload["scope"]["kind"], CAMPUS)
        self.assertEqual(payload["scope"]["label"], "Campus A")
        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {approver.pk, colleague.pk})
        self.assertNotIn(other.pk, ids)

    def test_an_institution_approver_sees_administration_teams_only(self):
        admin = make_team("Central Administration", ("supervisor",))
        academic = make_team("Campus A Faculty", ("supervisor",), campus="Campus A")

        approver = make_employee("institution-approver@on-leave.test", team=admin)
        RoleAssignment.objects.create(role=self.roles["registrar"], user=approver)
        self.approved(approver)
        admin_colleague, _ = self.employee_on(admin.workflow, "admin-colleague")
        academic_colleague, _ = self.employee_on(
            academic.workflow, "academic-colleague"
        )

        payload = self.payload(approver)

        self.assertEqual(payload["scope"]["kind"], INSTITUTION)
        self.assertEqual(payload["scope"]["label"], "Administration teams")
        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {approver.pk, admin_colleague.pk})
        self.assertNotIn(academic_colleague.pk, ids)

    def test_a_scoped_role_granted_institution_wide_does_not_widen_the_scope(self):
        """Only a role marked institution-wide is an institution-wide holding.

        The write path already refuses the combination, but the read scope must
        not widen on a row it did not expect: a stray ``RoleAssignment`` for a
        scoped role is still not an institution-wide office.
        """
        team = make_team("Registry", ("supervisor",))
        person = make_employee("scoped-holder@on-leave.test", team=team)
        RoleAssignment.objects.create(
            role=ensure_roles("supervisor")["supervisor"], user=person
        )

        self.assertEqual(resolve_scope(person).kind, CHAIN)

    def test_hr_sees_every_approved_application(self):
        hr = User.objects.create_user(
            username="hr@on-leave.test",
            email="hr@on-leave.test",
            password="testpass123",
            role=User.Role.HR,
        )
        first, _ = self.employee_on(
            make_team("Registry", ("supervisor",)).workflow, "hr-sees-one"
        )
        second, _ = self.employee_on(
            make_team("Campus A Faculty", ("supervisor",), campus="Campus A").workflow,
            "hr-sees-two",
        )

        payload = self.payload(hr)

        self.assertEqual(payload["scope"]["kind"], ORGANISATION)
        self.assertEqual(payload["scope"]["label"], "Everyone")
        ids = {row["employee"]["id"] for row in payload["results"]}
        self.assertEqual(ids, {first.pk, second.pk})

    def test_a_superuser_is_treated_as_hr(self):
        root = User.objects.create_superuser(
            username="root@on-leave.test",
            email="root@on-leave.test",
            password="testpass123",
        )
        self.employee_on(make_team("Registry", ("supervisor",)).workflow, "someone")

        self.assertEqual(resolve_scope(root).kind, ORGANISATION)

    def test_a_wider_rung_wins_over_a_narrower_one(self):
        """A manager who is also HR sees the institution, not their team."""
        team = make_team("Registry", ("supervisor",))
        hr = User.objects.create_user(
            username="hr-manager@on-leave.test",
            email="hr-manager@on-leave.test",
            password="testpass123",
            role=User.Role.HR,
        )
        EmployeeProfile.objects.create(user=hr, team=team, grade="B")
        TeamRoleAssignment.objects.create(
            team=team,
            role=self.roles["supervisor"],
            user=hr,
            is_team_manager=True,
        )

        self.assertEqual(resolve_scope(hr).kind, ORGANISATION)


class ListingTests(OnLeaveTestBase):
    """What a row says, and which rows the screen lists by default."""

    def setUp(self):
        super().setUp()
        self.hr = User.objects.create_user(
            username="hr-listing@on-leave.test",
            email="hr-listing@on-leave.test",
            password="testpass123",
            role=User.Role.HR,
        )
        self.team = make_team("Registry", ("supervisor",))
        self.owner = make_employee(
            "listing-owner@on-leave.test",
            team=self.team,
            first_name="Amina",
            last_name="Banda",
        )

    def test_only_approved_applications_are_listed(self):
        for state in (
            LeaveApplication.Status.DRAFT,
            LeaveApplication.Status.SUBMITTED,
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.CANCELLED,
        ):
            self.approved(self.owner, status=state)
        approved = self.approved(self.owner)

        payload = self.payload(self.hr)

        self.assertEqual(
            [row["id"] for row in payload["results"]], [str(approved.pk)]
        )

    def test_leave_dates_are_split_into_on_leave_and_upcoming(self):
        self.approved(
            self.owner,
            start=TODAY - timedelta(days=1),
            end=TODAY + timedelta(days=1),
        )
        self.approved(
            self.owner,
            start=TODAY + timedelta(days=5),
            end=TODAY + timedelta(days=6),
        )

        payload = self.payload(self.hr)

        self.assertEqual(
            payload["counts"], {"on_leave": 1, "upcoming": 1, "returned": 0}
        )
        self.assertEqual(
            [row["state"] for row in payload["results"]], ["on_leave", "upcoming"]
        )

    def test_on_leave_rows_come_before_upcoming_rows(self):
        upcoming = self.approved(
            self.owner, start=TODAY + timedelta(days=2), end=TODAY + timedelta(days=3)
        )
        current = self.approved(self.owner, start=TODAY, end=TODAY + timedelta(days=1))

        rows = self.payload(self.hr)["results"]

        self.assertEqual(rows[0]["id"], str(current.pk))
        self.assertEqual(rows[1]["id"], str(upcoming.pk))

    def test_returned_leave_is_hidden_unless_past_is_asked_for(self):
        self.approved(
            self.owner, start=TODAY - timedelta(days=10), end=TODAY - timedelta(days=8)
        )

        default = self.payload(self.hr)
        with_past = self.payload(self.hr, include_past=True)

        self.assertEqual(default["results"], [])
        self.assertEqual(default["counts"]["returned"], 0)
        self.assertEqual(with_past["counts"]["returned"], 1)
        self.assertEqual(with_past["results"][0]["state"], "returned")

    def test_a_past_row_is_ordered_most_recent_first(self):
        older = self.approved(
            self.owner, start=TODAY - timedelta(days=30), end=TODAY - timedelta(days=28)
        )
        newer = self.approved(
            self.owner, start=TODAY - timedelta(days=5), end=TODAY - timedelta(days=3)
        )

        rows = self.payload(self.hr, include_past=True)["results"]

        self.assertEqual([row["id"] for row in rows], [str(newer.pk), str(older.pk)])

    def test_search_matches_a_name_or_an_email(self):
        other = make_employee(
            "other-listing@on-leave.test", team=self.team,
            first_name="Grace", last_name="Phiri",
        )
        mine = self.approved(self.owner)
        theirs = self.approved(other)

        by_name = self.payload(self.hr, query="Amina")
        by_email = self.payload(self.hr, query="other-listing@")
        no_match = self.payload(self.hr, query="nobody")

        self.assertEqual([row["id"] for row in by_name["results"]], [str(mine.pk)])
        self.assertEqual([row["id"] for row in by_email["results"]], [str(theirs.pk)])
        self.assertEqual(no_match["results"], [])

    def test_a_row_carries_the_employee_and_leave_context(self):
        application = self.approved(
            self.owner, start=TODAY, end=TODAY + timedelta(days=2)
        )

        row = self.payload(self.hr)["results"][0]

        self.assertEqual(row["reference_number"], application.reference_number)
        self.assertEqual(
            row["employee"],
            {
                "id": self.owner.pk,
                "full_name": "Amina Banda",
                "designation": "",
                "team": self.team.name,
                "campus": "",
            },
        )
        self.assertEqual(
            row["leave_type"], {"id": self.annual.pk, "name": "Annual Leave"}
        )
        self.assertEqual(row["start_date"], TODAY.isoformat())
        self.assertEqual(row["end_date"], (TODAY + timedelta(days=2)).isoformat())
        self.assertEqual(row["working_days"], 3)

    def test_an_anonymous_caller_covers_nobody(self):
        self.approved(self.owner)

        payload = on_leave_payload(user=AnonymousUser(), today=TODAY)

        self.assertEqual(payload["scope"]["kind"], SELF)
        self.assertEqual(payload["results"], [])


class OnLeaveEndpointTests(OnLeaveTestBase):
    """The HTTP surface: authentication, filters, and the scope description."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.team = make_team("Registry", ("supervisor",))
        self.owner = make_employee("api-owner@on-leave.test", team=self.team)
        self.today = timezone.localdate()

    def test_requires_authentication(self):
        response = APIClient().get(URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_the_signed_in_users_scope(self):
        self.approved(self.owner, start=self.today, end=self.today)
        self.client.force_authenticate(user=self.owner)

        # Enrol the owner on their team's workflow so they route through a chain
        from chains.models import WorkflowMember
        WorkflowMember.objects.create(
            workflow=self.owner.employee_profile.team.workflow,
            user=self.owner,
            team=self.owner.employee_profile.team,
            is_wide_approver=False,
        )

        response = self.client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["today"], self.today.isoformat())
        self.assertEqual(response.data["scope"]["kind"], CHAIN)
        self.assertTrue(response.data["scope"]["description"])
        self.assertEqual(response.data["counts"]["on_leave"], 1)

    def test_include_past_accepts_a_truthy_query_value(self):
        self.approved(
            self.owner,
            start=self.today - timedelta(days=10),
            end=self.today - timedelta(days=8),
        )
        self.client.force_authenticate(user=self.owner)

        self.assertEqual(self.client.get(URL).data["results"], [])
        for value in ("1", "true", "yes", "on"):
            with self.subTest(value=value):
                payload = self.client.get(f"{URL}?include_past={value}").data
                self.assertEqual(len(payload["results"]), 1)

    def test_include_past_ignores_a_false_value(self):
        self.approved(
            self.owner,
            start=self.today - timedelta(days=10),
            end=self.today - timedelta(days=8),
        )
        self.client.force_authenticate(user=self.owner)

        self.assertEqual(
            self.client.get(f"{URL}?include_past=false").data["results"], []
        )

    def test_search_is_forwarded(self):
        self.approved(self.owner, start=self.today, end=self.today)
        self.client.force_authenticate(user=self.owner)

        self.assertEqual(len(self.client.get(f"{URL}?q=owner").data["results"]), 1)
        self.assertEqual(self.client.get(f"{URL}?q=nobody").data["results"], [])

    def test_a_long_search_is_truncated_rather_than_refused(self):
        self.approved(self.owner, start=self.today, end=self.today)
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(f"{URL}?q={'a' * 500}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_only_get_is_allowed(self):
        self.client.force_authenticate(user=self.owner)

        self.assertEqual(
            self.client.post(URL, {}).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
