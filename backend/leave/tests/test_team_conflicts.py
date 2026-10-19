"""UI/UX Phase 2 — the hard-block team conflict rule.

The refusal ``decide`` applies when an approval would leave the applicant's
team over-subscribed, read from the same numbers as ``leave.conflicts``.
"""

import math
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from leave.conflicts import conflict_threshold, find_team_conflict
from leave.models import LeaveApplication
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user
from users.models import EmployeeProfile
from approvals.models import ApplicationStage
from approvals.services import ApprovalConflictError, decide
from workflows.testing import team_for

User = get_user_model()


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


class ConflictThresholdTests(TestCase):
    """The cap is ``max(1, ceil(0.3 × team size))`` and never below one."""

    def test_a_small_team_can_never_be_conflicted_by_arithmetic(self):
        self.assertEqual(conflict_threshold(0), 1)
        self.assertEqual(conflict_threshold(1), 1)
        self.assertEqual(conflict_threshold(2), 1)

    def test_the_cap_is_thirty_percent_rounded_up(self):
        for size in range(3, 40):
            self.assertEqual(conflict_threshold(size), max(1, math.ceil(0.3 * size)))


class TeamConflictDecisionTests(StubProviderMixin, APITestCase):
    """``decide`` refuses an approve that would over-subscribe the team."""

    def setUp(self):
        self.stub = self.use_stub()
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


class FindTeamConflictTests(StubProviderMixin, TestCase):
    """The pure rule: a team of one is never conflicted; overlapping counts."""

    def setUp(self):
        self.stub = self.use_stub()
        self.team = team_for("Administration")

    def test_no_dates_is_never_a_conflict(self):
        employee = _employee(f"solo-{uuid4().hex[:6]}@luanar", self.team)
        app = LeaveApplication.objects.create(
            employee=employee, leave_type_id=1, reason="No dates"
        )
        self.assertIsNone(find_team_conflict(app))

    def test_a_team_of_one_is_never_a_conflict(self):
        employee = _employee(f"solo2-{uuid4().hex[:6]}@luanar", self.team)
        start = EARLIEST_ANNUAL_START
        app = _application(
            employee,
            start=start,
            end=start + timedelta(days=1),
            status_value=LeaveApplication.Status.SUBMITTED,
        )
        self.assertIsNone(find_team_conflict(app))
