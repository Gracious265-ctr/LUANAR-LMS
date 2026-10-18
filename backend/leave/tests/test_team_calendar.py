"""UI/UX Phase 2 — team calendar and the hard-block team conflict rule.

Two surfaces over one number (``leave.conflicts``): the calendar endpoint that
an approver reads, and the refusal ``decide`` applies when an approval would
leave the team over-subscribed.
"""

from datetime import date, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from leave.models import LeaveApplication
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user
from users.models import EmployeeProfile
from approvals.models import ApplicationStage
from approvals.services import ApprovalConflictError, decide
from workflows.testing import make_team

User = get_user_model()

CALENDAR_URL = "/api/v1/calendar/team/"
MONTH = "2026-10"


def _employee(username, team, **kwargs):
    user = make_user(username, role=User.Role.EMPLOYEE, **kwargs)
    EmployeeProfile.objects.create(user=user, team=team, grade="B")
    return user


def _application(employee, *, start, end, status_value):
    return LeaveApplication.objects.create(
        employee=employee,
        leave_type_id=1,
        start_date=start,
        end_date=end,
        status=status_value,
        reason="Test",
    )


class TeamCalendarAccessTests(APITestCase):
    def setUp(self):
        self.hr = make_user("hr@luanar", role=User.Role.HR)
        self.team = make_team("Finance", ["supervisor"], campus=None)
        self.supervisor = self.team.workflow.sections.get(
            approver_role__code="supervisor"
        ).approver
        self.member = _employee("member@luanar", self.team)
        self.outsider = _employee("outsider@luanar", None)

    def _get(self, *, team_id, month=MONTH, user=None):
        if user is not None:
            self.client.force_authenticate(user)
        return self.client.get(
            CALENDAR_URL, {"unit_id": team_id, "month": month}
        )

    def test_missing_parameters_are_rejected(self):
        self.client.force_authenticate(self.hr)
        self.assertEqual(
            self.client.get(CALENDAR_URL).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(CALENDAR_URL, {"unit_id": self.team.pk}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(
                CALENDAR_URL, {"unit_id": self.team.pk, "month": "nonsense"}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unknown_or_out_of_scope_team_is_404(self):
        response = self._get(team_id=999999, user=self.hr)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # An employee on another team (here, no team) may not read this one.
        response = self._get(team_id=self.team.pk, user=self.outsider)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_may_read_any_team(self):
        response = self._get(team_id=self.team.pk, user=self.hr)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unit_name"], "Finance")

    def test_member_reads_their_own_team(self):
        response = self._get(team_id=self.team.pk, user=self.member)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_section_approver_reads_the_team_they_approve_for(self):
        response = self._get(team_id=self.team.pk, user=self.supervisor)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TeamCalendarContentTests(APITestCase):
    def setUp(self):
        self.team = make_team("Finance", ["supervisor"], campus=None)
        self.supervisor = self.team.workflow.sections.get(
            approver_role__code="supervisor"
        ).approver
        self.inside = _employee("inside@luanar", self.team, first_name="Ina")
        self.approved = _employee("approved@luanar", self.team, first_name="Aya")

    def _entries(self):
        response = self.client.get(
            CALENDAR_URL, {"unit_id": self.team.pk, "month": MONTH}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_only_approved_and_pending_leave_of_this_team_in_the_month(self):
        self.client.force_authenticate(self.supervisor)

        pending = _application(
            self.inside,
            start=date(2026, 10, 5),
            end=date(2026, 10, 9),
            status_value=LeaveApplication.Status.SUBMITTED,
        )
        approved = _application(
            self.approved,
            start=date(2026, 10, 12),
            end=date(2026, 10, 14),
            status_value=LeaveApplication.Status.APPROVED,
        )
        # Spans into the month, so it is an entry even though it starts before it.
        overlapping = _application(
            self.inside,
            start=date(2026, 9, 28),
            end=date(2026, 10, 2),
            status_value=LeaveApplication.Status.SUBMITTED,
        )
        # Excluded states and window.
        _application(
            self.inside,
            start=date(2026, 10, 5),
            end=date(2026, 10, 6),
            status_value=LeaveApplication.Status.REJECTED,
        )
        _application(
            self.inside,
            start=date(2026, 10, 5),
            end=date(2026, 10, 6),
            status_value=LeaveApplication.Status.CANCELLED,
        )
        _application(
            self.inside,
            start=date(2026, 10, 5),
            end=date(2026, 10, 6),
            status_value=LeaveApplication.Status.DRAFT,
        )
        _application(
            self.inside,
            start=date(2026, 11, 2),
            end=date(2026, 11, 5),
            status_value=LeaveApplication.Status.APPROVED,
        )
        other_team = _employee("other@luanar", None)
        _application(
            other_team,
            start=date(2026, 10, 5),
            end=date(2026, 10, 6),
            status_value=LeaveApplication.Status.APPROVED,
        )

        data = self._entries()
        ids = {entry["id"] for entry in data["entries"]}
        self.assertEqual(
            ids, {str(pending.pk), str(approved.pk), str(overlapping.pk)}
        )
        by_id = {entry["id"]: entry for entry in data["entries"]}
        self.assertEqual(by_id[str(pending.pk)]["status"], "pending")
        self.assertEqual(by_id[str(approved.pk)]["status"], "approved")
        self.assertEqual(
            by_id[str(pending.pk)]["employee"]["id"], self.inside.pk
        )

    def test_empty_month_returns_no_entries_and_the_conflict_cap(self):
        self.client.force_authenticate(self.supervisor)
        data = self._entries()
        self.assertEqual(data["entries"], [])
        self.assertEqual(data["month"], MONTH)
        self.assertIn("team_size", data)
        self.assertIn("conflict_threshold", data)

    def test_conflict_threshold_matches_the_shared_rule(self):
        from leave.conflicts import conflict_threshold

        self.client.force_authenticate(self.supervisor)
        data = self._entries()
        self.assertEqual(
            data["conflict_threshold"], conflict_threshold(data["team_size"])
        )


class TeamConflictDecisionTests(StubProviderMixin, APITestCase):
    """``decide`` refuses an approve that would over-subscribe the team."""

    def setUp(self):
        self.stub = self.use_stub()
        from workflows.testing import team_for

        self.team = team_for("Administration")
        self.employee = make_user(
            "conflict-employee@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        EmployeeProfile.objects.create(user=self.employee, team=self.team, grade="B")
        self.supervisor = make_user(
            "conflict-supervisor@luanar", role="supervisor", first_name="Sana"
        )
        EmployeeProfile.objects.create(
            user=self.supervisor, team=self.team, grade="E"
        )
        self.stub.register_employee(self.employee)
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", make_user("conflict-hod@luanar", role="hod")),
            ("registrar", make_user("conflict-registrar@luanar", role="registrar")),
            ("dvc", make_user("conflict-dvc@luanar", role="dvc")),
        ):
            self.stub.workflow.register_approver(role, user)

    def _submit(self):
        from leave.services.submission import submit_application

        start = EARLIEST_ANNUAL_START
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=start,
            end_date=start + timedelta(days=3),
            reason="Family visit",
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def _stage_version(self, app):
        return ApplicationStage.objects.get(
            application=app, submission_cycle=app.submission_cycle, stage_order=1
        ).decision_version

    def _add_overlapping_colleague_leave(self, status_value):
        colleague = make_user(
            f"colleague-{uuid4().hex[:8]}@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Col",
            last_name="League",
        )
        EmployeeProfile.objects.create(user=colleague, team=self.team, grade="B")
        start = EARLIEST_ANNUAL_START
        return _application(
            colleague,
            start=start,
            end=start + timedelta(days=2),
            status_value=status_value,
        )

    def test_approve_is_blocked_when_the_day_goes_over_the_cap(self):
        app = self._submit()
        self._add_overlapping_colleague_leave(LeaveApplication.Status.APPROVED)
        with self.assertRaises(ApprovalConflictError) as caught:
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action="approve",
                expected_version=self._stage_version(app),
            )
        self.assertEqual(caught.exception.conflict.out_count, 2)
        # Nothing was written: the application is still open at stage one.
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)

    def test_approve_succeeds_within_the_cap(self):
        app = self._submit()
        result = decide(
            application_id=app.pk,
            actor=self.supervisor,
            action="approve",
            expected_version=self._stage_version(app),
        )
        self.assertEqual(result.status, LeaveApplication.Status.SUBMITTED)
        stage = ApplicationStage.objects.get(
            application=app, stage_order=1
        )
        self.assertEqual(stage.status, ApplicationStage.Status.APPROVED)

    def test_reject_is_never_blocked_by_a_conflict(self):
        app = self._submit()
        self._add_overlapping_colleague_leave(LeaveApplication.Status.APPROVED)
        result = decide(
            application_id=app.pk,
            actor=self.supervisor,
            action="reject",
            comment="Team cover unavailable.",
            expected_version=self._stage_version(app),
        )
        self.assertEqual(result.status, LeaveApplication.Status.REJECTED)
