"""Tests for Leave Plans (refinement unit 04).

Covers the three surfaces the unit introduces:

* the owner's plan CRUD and the "Apply Now" handoff to a leave draft,
* the assignment-driven team calendar and its scope authorisation,
* the daily reminder/follow-up/missed job and the launcher entry.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from launcher.services import _plans_badge, can_access_plans
from leave.models import FinancialYear, LeaveApplication
from leave_config.models import LeaveType
from notifications.models import NotificationOutbox
from notifications.plans import PLAN_FOLLOW_UP, PLAN_REMINDER
from plans.models import LeavePlan, LeavePlanStatus
from plans.services import resolve_scopes
from plans.tasks import FOLLOW_UP_AFTER_DAYS, check_and_notify_plans
from users.models import EmployeeProfile
from workflows.models import (
    Campus,
    CampusRoleAssignment,
    RoleAssignment,
    Team,
    TeamRoleAssignment,
)
from workflows.testing import ensure_roles, team_for

User = get_user_model()

LIST_URL = "/api/v1/plans/"


class PlansTestBase(TestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.fy = FinancialYear.objects.create(
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=185),
            is_active=True,
        )
        self.leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", plannable=True, notice_days=7
        )
        self.team = team_for("Administration Team")
        self.user = self._employee("employee@test.luanar")
        self.other = self._employee("other@test.luanar", team=team_for("Finance Team"))
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _employee(self, username: str, *, team: Team | None = None) -> User:
        user = User.objects.create_user(
            username=username, email=username, password="testpass123"
        )
        EmployeeProfile.objects.create(
            user=user,
            team=team or self.team,
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
        )
        return user

    def _plan(self, user=None, **overrides) -> LeavePlan:
        defaults = {
            "employee": user or self.user,
            "leave_type": self.leave_type,
            "financial_year": self.fy,
            "planned_start_date": self.today + timedelta(days=30),
            "planned_end_date": self.today + timedelta(days=34),
        }
        defaults.update(overrides)
        return LeavePlan.objects.create(**defaults)

    def _post_plan(self, **overrides):
        payload = {
            "leave_type": self.leave_type.pk,
            "financial_year": self.fy.pk,
            "planned_start_date": (self.today + timedelta(days=30)).isoformat(),
            "planned_end_date": (self.today + timedelta(days=34)).isoformat(),
            "notes": "Family trip",
        }
        payload.update(overrides)
        return self.client.post(LIST_URL, payload, format="json")


class PlanCreateTests(PlansTestBase):
    def test_create_persists_an_open_plan(self):
        response = self._post_plan()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LeavePlan.objects.count(), 1)
        plan = LeavePlan.objects.get()
        self.assertEqual(plan.employee, self.user)
        self.assertEqual(plan.status, LeavePlanStatus.UPCOMING)
        self.assertEqual(plan.notes, "Family trip")

    def test_non_plannable_type_is_rejected(self):
        self.leave_type.plannable = False
        self.leave_type.save(update_fields=["plannable"])

        response = self._post_plan()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("leave_type", response.json())
        self.assertEqual(LeavePlan.objects.count(), 0)

    def test_end_before_start_is_rejected(self):
        response = self._post_plan(
            planned_start_date=(self.today + timedelta(days=10)).isoformat(),
            planned_end_date=(self.today + timedelta(days=5)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("planned_end_date", response.json())

    def test_overlap_with_existing_plan_warns_but_still_creates(self):
        self._plan()

        response = self._post_plan()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("overlap_warning", response.json())
        self.assertEqual(LeavePlan.objects.count(), 2)

    def test_overlap_with_existing_application_warns(self):
        LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=self.leave_type.pk,
            start_date=self.today + timedelta(days=31),
            end_date=self.today + timedelta(days=32),
            status=LeaveApplication.Status.SUBMITTED,
        )

        response = self._post_plan()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("overlap_warning", response.json())

    def test_financial_year_defaults_when_omitted(self):
        payload = {
            "leave_type": self.leave_type.pk,
            "planned_start_date": (self.today + timedelta(days=30)).isoformat(),
            "planned_end_date": (self.today + timedelta(days=34)).isoformat(),
        }

        response = self.client.post(LIST_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LeavePlan.objects.get().financial_year, self.fy)


class PlanOwnershipTests(PlansTestBase):
    def test_list_only_returns_own_plans(self):
        self._plan(user=self.user)
        self._plan(user=self.other)

        response = self.client.get(LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"] if "results" in response.json() else response.json()
        self.assertEqual(len(results), 1)

    def test_retrieving_another_users_plan_is_404(self):
        plan = self._plan(user=self.other)

        response = self.client.get(f"{LIST_URL}{plan.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_own_plan(self):
        plan = self._plan()

        response = self.client.delete(f"{LIST_URL}{plan.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LeavePlan.objects.filter(pk=plan.pk).exists())


class PlanApplyTests(PlansTestBase):
    def test_apply_creates_a_draft_linked_to_the_plan(self):
        plan = self._plan()

        response = self.client.post(f"{LIST_URL}{plan.pk}/apply/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        application = LeaveApplication.objects.get(pk=response.json()["application_id"])
        self.assertEqual(application.status, LeaveApplication.Status.DRAFT)
        self.assertEqual(application.source_plan_id, plan.pk)
        self.assertEqual(application.leave_type_id, self.leave_type.pk)
        self.assertEqual(application.start_date, plan.planned_start_date)
        plan.refresh_from_db()
        self.assertEqual(plan.status, LeavePlanStatus.CONVERTED)
        self.assertEqual(plan.converted_application_id, application.pk)

    def test_apply_is_idempotent(self):
        plan = self._plan()

        first = self.client.post(f"{LIST_URL}{plan.pk}/apply/").json()
        second = self.client.post(f"{LIST_URL}{plan.pk}/apply/").json()

        self.assertEqual(first["application_id"], second["application_id"])
        self.assertEqual(LeaveApplication.objects.count(), 1)

    def test_cancelled_plan_cannot_be_applied(self):
        plan = self._plan(status=LeavePlanStatus.CANCELLED)

        response = self.client.post(f"{LIST_URL}{plan.pk}/apply/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_apply_another_users_plan(self):
        plan = self._plan(user=self.other)

        response = self.client.post(f"{LIST_URL}{plan.pk}/apply/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ScopeResolutionTests(PlansTestBase):
    def test_employee_scope_is_their_own_team(self):
        scopes = resolve_scopes(self.user)

        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].token, f"team:{self.team.pk}")
        self.assertEqual(scopes[0].team_ids, frozenset({self.team.pk}))

    def test_campus_role_widens_scope_to_the_campus(self):
        campus = Campus.objects.create(name="Main Campus", code="main")
        self.team.campus = campus
        self.team.save(update_fields=["campus"])
        partner = team_for("Partner Team")
        partner.campus = campus
        partner.save(update_fields=["campus"])
        role = ensure_roles("campus_registrar")["campus_registrar"]
        CampusRoleAssignment.objects.create(campus=campus, role=role, user=self.user)

        scopes = resolve_scopes(self.user)

        tokens = {scope.token for scope in scopes}
        self.assertIn(f"campus:{campus.pk}", tokens)

    def test_institution_role_sees_every_team(self):
        role = ensure_roles("registrar")["registrar"]
        RoleAssignment.objects.create(user=self.user, role=role)

        scopes = resolve_scopes(self.user)

        institution = [s for s in scopes if s.token == "institution"]
        self.assertEqual(len(institution), 1)
        self.assertEqual(
            institution[0].team_ids,
            frozenset(Team.objects.values_list("pk", flat=True)),
        )

    def test_team_role_holder_sees_that_team(self):
        role = ensure_roles("hod")["hod"]
        TeamRoleAssignment.objects.create(team=self.team, role=role, user=self.user)

        scopes = resolve_scopes(self.user)

        self.assertTrue(
            any(scope.token == f"team:{self.team.pk}" for scope in scopes)
        )


class TeamCalendarTests(PlansTestBase):
    def test_scope_options_lists_the_default_team(self):
        response = self.client.get("/api/v1/plans/scope-options/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()[0]["id"], f"team:{self.team.pk}")

    def test_default_calendar_shows_teammates_plans(self):
        self._plan(user=self.other, employee=self.other)
        teammate = self._employee("mate@test.luanar")
        self._plan(user=teammate, employee=teammate)
        # A plan outside the team must never leak in.
        outsider = self._employee("outsider@test.luanar", team=team_for("Other Team"))
        self._plan(user=outsider, employee=outsider)
        month = (self.today + timedelta(days=30)).strftime("%Y-%m")

        response = self.client.get(f"/api/v1/plans/team/?month={month}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        names = {row["employee_name"] for row in body["results"]}
        self.assertIn(teammate.username, names)
        self.assertNotIn(outsider.username, names)

    def test_out_of_scope_token_is_404(self):
        response = self.client.get("/api/v1/plans/team/?scope=institution")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_bad_month_is_rejected(self):
        response = self.client.get("/api/v1/plans/team/?month=not-a-month")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PlanTaskTests(PlansTestBase):
    def test_reminder_fires_inside_the_notice_window(self):
        plan = self._plan(
            planned_start_date=self.today + timedelta(days=3),
            planned_end_date=self.today + timedelta(days=5),
        )

        result = check_and_notify_plans()

        plan.refresh_from_db()
        self.assertEqual(plan.status, LeavePlanStatus.NOTIFIED)
        self.assertIsNotNone(plan.notified_at)
        self.assertEqual(result["reminders"], 1)
        self.assertTrue(
            NotificationOutbox.objects.filter(
                plan=plan, kind=PLAN_REMINDER
            ).exists()
        )

    def test_reminder_does_not_fire_outside_the_window(self):
        plan = self._plan(
            planned_start_date=self.today + timedelta(days=60),
            planned_end_date=self.today + timedelta(days=62),
        )

        check_and_notify_plans()

        plan.refresh_from_db()
        self.assertEqual(plan.status, LeavePlanStatus.UPCOMING)

    def test_reminder_is_idempotent_across_runs(self):
        self._plan(
            planned_start_date=self.today + timedelta(days=3),
            planned_end_date=self.today + timedelta(days=5),
        )

        check_and_notify_plans()
        check_and_notify_plans()

        self.assertEqual(
            NotificationOutbox.objects.filter(kind=PLAN_REMINDER).count(), 1
        )

    def test_follow_up_fires_after_the_delay(self):
        plan = self._plan(
            status=LeavePlanStatus.NOTIFIED,
            planned_start_date=self.today + timedelta(days=10),
            planned_end_date=self.today + timedelta(days=12),
            notified_at=timezone.now() - timedelta(days=FOLLOW_UP_AFTER_DAYS + 1),
        )

        check_and_notify_plans()

        plan.refresh_from_db()
        self.assertIsNotNone(plan.follow_up_sent_at)
        self.assertTrue(
            NotificationOutbox.objects.filter(
                plan=plan, kind=PLAN_FOLLOW_UP
            ).exists()
        )

    def test_past_plan_is_marked_missed(self):
        plan = self._plan(
            planned_start_date=self.today - timedelta(days=10),
            planned_end_date=self.today - timedelta(days=8),
        )

        check_and_notify_plans()

        plan.refresh_from_db()
        self.assertEqual(plan.status, LeavePlanStatus.MISSED)


class LauncherTests(PlansTestBase):
    def test_all_authenticated_users_can_access_plans(self):
        self.assertTrue(can_access_plans(self.user))

    def test_badge_counts_only_notified_plans(self):
        self._plan(status=LeavePlanStatus.NOTIFIED)
        self._plan(status=LeavePlanStatus.UPCOMING)
        self._plan(status=LeavePlanStatus.MISSED)

        self.assertEqual(
            _plans_badge(self.user), {"count": 1, "label": "ready to apply"}
        )

    def test_badge_absent_when_nothing_to_do(self):
        self._plan(status=LeavePlanStatus.UPCOMING)

        self.assertIsNone(_plans_badge(self.user))
