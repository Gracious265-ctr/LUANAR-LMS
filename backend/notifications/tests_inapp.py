"""In-app notification feed tests (refinement unit 08).

Three layers, each asserting the durable truth (a ``Notification`` row):

* the service seam — creation, per-user scoping, and the read/mark mutations;
* the HTTP surface — auth, ownership (a foreign id is 404 and changes nothing),
  and the badge/list payloads;
* the real wiring — a submission and every decision through the *actual*
  ``submit_application``/``decide`` services with the stub rules provider, plus
  the daily Leave Plans job, so §2.1's table is verified end to end rather than
  by calling the consumers directly.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from approvals.models import ApprovalDecision
from approvals.services import decide
from leave.models import FinancialYear, LeaveApplication
from leave.services.resubmission import resubmit_application
from leave.services.submission import submit_application
from leave.tests.stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user
from leave_types.models import LeaveType
from notifications.models import Notification
from notifications.services import (
    create_notification,
    get_recent_notifications,
    get_unread_count,
    mark_all_read,
    mark_read,
    queue_decision_notification,
)
from plans.models import LeavePlan
from plans.tasks import FOLLOW_UP_AFTER_DAYS, check_and_notify_plans
from teams.models import Team
from users.models import EmployeeProfile
from chains.events import (
    _reset_consumers_for_tests,
    register_consumer,
)
from chains.testing import team_for

User = get_user_model()


class NotificationServiceTests(TestCase):
    """The module seam: one row per call, every read/mutation recipient-scoped."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username=f"alice-{uuid4().hex[:8]}", email="alice@test.luanar"
        )
        self.bob = User.objects.create_user(
            username=f"bob-{uuid4().hex[:8]}", email="bob@test.luanar"
        )

    def _notification(self, recipient, **overrides):
        is_read = overrides.pop("is_read", False)
        defaults = {
            "recipient": recipient,
            "event_type": "application.approved",
            "message": "Your Annual Leave application was approved",
            "link": f"/applications/{uuid4()}",
        }
        defaults.update(overrides)
        row = create_notification(**defaults)
        if is_read:
            row.is_read = True
            row.save(update_fields=["is_read"])
        return row

    def test_create_notification_persists_the_row(self):
        link = f"/applications/{uuid4()}"

        row = self._notification(
            self.alice,
            event_type="application.rejected",
            message="Your Annual Leave application was rejected",
            link=link,
        )

        row.refresh_from_db()
        self.assertEqual(row.recipient, self.alice)
        self.assertEqual(row.event_type, "application.rejected")
        self.assertEqual(row.message, "Your Annual Leave application was rejected")
        self.assertEqual(row.link, link)
        self.assertFalse(row.is_read)

    def test_recent_and_unread_count_are_scoped_per_user(self):
        self._notification(self.alice)
        self._notification(self.alice, is_read=True)
        self._notification(self.bob)

        self.assertEqual(len(get_recent_notifications(self.alice)), 2)
        self.assertEqual(get_unread_count(self.alice), 1)
        self.assertEqual(len(get_recent_notifications(self.bob)), 1)
        self.assertEqual(get_unread_count(self.bob), 1)

    def test_recent_is_newest_first_and_honours_the_limit(self):
        older = self._notification(self.alice)
        newer = self._notification(self.alice)

        recent = get_recent_notifications(self.alice, limit=1)

        self.assertEqual(recent, [newer])
        self.assertNotIn(older, recent)

    def test_recent_unread_only_filters_before_the_limit(self):
        for _ in range(3):
            self._notification(self.alice, is_read=True)
        unread = [self._notification(self.alice) for _ in range(2)]

        recent = get_recent_notifications(self.alice, limit=3, unread_only=True)

        self.assertEqual(set(recent), set(unread))

    def test_mark_read_only_affects_the_named_row(self):
        first = self._notification(self.alice)
        second = self._notification(self.alice)

        mark_read(str(first.pk), self.alice)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertFalse(second.is_read)

    def test_mark_read_ignores_another_users_notification(self):
        bob_row = self._notification(self.bob)

        mark_read(str(bob_row.pk), self.alice)

        bob_row.refresh_from_db()
        self.assertFalse(bob_row.is_read)

    def test_mark_all_read_only_touches_the_callers_rows(self):
        self._notification(self.alice)
        self._notification(self.alice)
        bob_row = self._notification(self.bob)

        mark_all_read(self.alice)

        self.assertEqual(get_unread_count(self.alice), 0)
        bob_row.refresh_from_db()
        self.assertFalse(bob_row.is_read)


class NotificationAPITests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username=f"alice-{uuid4().hex[:8]}", email="alice@test.luanar"
        )
        self.bob = User.objects.create_user(
            username=f"bob-{uuid4().hex[:8]}", email="bob@test.luanar"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def _notification(self, recipient, **overrides):
        is_read = overrides.pop("is_read", False)
        defaults = {
            "recipient": recipient,
            "event_type": "approval.assigned",
            "message": "A leave application needs your review: LV-1",
            "link": f"/dashboard/approvals/{uuid4()}",
        }
        defaults.update(overrides)
        row = create_notification(**defaults)
        if is_read:
            row.is_read = True
            row.save(update_fields=["is_read"])
        return row

    def test_list_returns_only_the_callers_notifications(self):
        own = self._notification(self.alice)
        self._notification(self.bob)

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], str(own.pk))
        self.assertEqual(body[0]["event_type"], "approval.assigned")
        self.assertIn("is_read", body[0])
        self.assertIn("created_at", body[0])

    def test_list_unread_only(self):
        self._notification(self.alice, is_read=True)
        unread = self._notification(self.alice)

        response = self.client.get("/api/v1/notifications/?unread_only=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual([row["id"] for row in body], [str(unread.pk)])

    def test_list_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unread_count_is_the_callers_only(self):
        self._notification(self.alice)
        self._notification(self.alice)
        self._notification(self.bob)

        response = self.client.get("/api/v1/notifications/unread-count/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"count": 2})

    def test_mark_read_marks_the_callers_row(self):
        row = self._notification(self.alice)

        response = self.client.post(f"/api/v1/notifications/{row.pk}/mark-read/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        row.refresh_from_db()
        self.assertTrue(row.is_read)

    def test_mark_read_cannot_touch_another_users_notification(self):
        bob_row = self._notification(self.bob)

        response = self.client.post(f"/api/v1/notifications/{bob_row.pk}/mark-read/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        bob_row.refresh_from_db()
        self.assertFalse(bob_row.is_read)

    def test_mark_read_unknown_id_is_404(self):
        response = self.client.post(
            f"/api/v1/notifications/{uuid4()}/mark-read/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read_clears_the_callers_badge(self):
        self._notification(self.alice)
        self._notification(self.alice)
        self._notification(self.bob)

        response = self.client.post("/api/v1/notifications/mark-all-read/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self.client.get("/api/v1/notifications/unread-count/").json()["count"], 0
        )
        self.assertEqual(get_unread_count(self.bob), 1)


class ApprovalNotificationTests(StubProviderMixin, TestCase):
    """§2.1's Approvals rows, through the real submit/decide services."""

    def setUp(self):
        _reset_consumers_for_tests()
        register_consumer(queue_decision_notification)

        self.stub = self.use_stub()
        self.employee = make_user(
            f"employee-{uuid4().hex[:8]}@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        self.supervisor = make_user(
            f"supervisor-{uuid4().hex[:8]}@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            f"hod-{uuid4().hex[:8]}@luanar", role="hod", first_name="Hady", last_name="Od"
        )
        self.registrar = make_user(
            f"registrar-{uuid4().hex[:8]}@luanar",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        self.dvc = make_user(
            f"dvc-{uuid4().hex[:8]}@luanar", role="dvc", first_name="Din", last_name="Vc"
        )
        self.stub.register_employee(self.employee)
        EmployeeProfile.objects.create(
            user=self.employee,
            designation="Junior Officer",
            team=team_for("Administration"),
            grade="B",
        )
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
            ("dvc", self.dvc),
        ):
            self.stub.workflow.register_approver(role, user)

    def _submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            reason="Family visit",
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def _for(self, user, event_type=None):
        rows = Notification.objects.filter(recipient=user)
        if event_type:
            rows = rows.filter(event_type=event_type)
        return rows

    def test_submission_notifies_the_opening_stage_approvers(self):
        app = self._submitted()

        rows = self._for(self.supervisor, "approval.assigned")
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.link, f"/dashboard/approvals/{app.pk}")
        self.assertIn(app.reference_number, row.message)
        # Only the opening section is pending, so nobody downstream hears about it.
        self.assertEqual(self._for(self.hod).count(), 0)
        self.assertEqual(self._for(self.employee).count(), 0)

    def test_intermediate_approval_notifies_the_next_stage_only(self):
        app = self._submitted()

        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )

        self.assertEqual(self._for(self.hod, "approval.assigned").count(), 1)
        # An intermediate approve is not "your application was approved".
        self.assertEqual(self._for(self.employee).count(), 0)

    def test_final_approval_notifies_the_employee(self):
        app = self._submitted()
        with self.captureOnCommitCallbacks(execute=True):
            for actor in (self.supervisor, self.hod, self.registrar, self.dvc):
                decide(
                    application_id=app.pk,
                    actor=actor,
                    action=ApprovalDecision.Action.APPROVE,
                    expected_version=1,
                )

        row = self._for(self.employee, "application.approved").get()
        self.assertEqual(row.link, f"/applications/{app.pk}")
        self.assertIn("was approved", row.message)

    def test_rejection_notifies_the_employee(self):
        app = self._submitted()

        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.REJECT,
                comment="Insufficient documentation.",
                expected_version=1,
            )

        row = self._for(self.employee, "application.rejected").get()
        self.assertIn("was rejected", row.message)

    def test_resubmission_reopens_the_stage_with_a_fresh_pending_item(self):
        app = self._submitted()
        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.pk,
                actor=self.supervisor,
                action=ApprovalDecision.Action.REJECT,
                comment="Insufficient documentation.",
                expected_version=1,
            )

        resubmit_application(user=self.employee, application_id=app.pk)

        self.assertEqual(self._for(self.supervisor, "approval.assigned").count(), 2)


class PlanReminderNotificationTests(TestCase):
    """§2.1's Leave Plans rows, through the real daily job."""

    def setUp(self):
        self.today = timezone.localdate()
        self.fy = FinancialYear.objects.create(
            start_date=self.today - timedelta(days=180),
            end_date=self.today + timedelta(days=185),
            is_active=True,
        )
        self.leave_type = LeaveType.objects.create(
            name="Annual Leave", code="annual", plannable=True, notice_days=7
        )
        self.employee = User.objects.create_user(
            username=f"planner-{uuid4().hex[:8]}", email="planner@test.luanar"
        )
        EmployeeProfile.objects.create(
            user=self.employee,
            team=Team.objects.create(
                name=f"Team {uuid4().hex[:6]}",
                code=f"t-{uuid4().hex[:6]}",
                status=Team.Status.ACTIVE,
            ),
            category=EmployeeProfile.Category.ADMINISTRATION,
            grade="B",
        )
        self.plan = LeavePlan.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            financial_year=self.fy,
            planned_start_date=self.today + timedelta(days=3),
            planned_end_date=self.today + timedelta(days=5),
        )

    def test_reminder_fires_an_in_app_notification(self):
        check_and_notify_plans()

        row = Notification.objects.get(recipient=self.employee)
        self.assertEqual(row.event_type, "plan.reminder")
        self.assertEqual(row.link, f"/dashboard/plans/{self.plan.pk}")
        self.assertIn("Annual Leave", row.message)

    def test_reminder_does_not_fire_outside_the_window(self):
        self.plan.planned_start_date = self.today + timedelta(days=60)
        self.plan.planned_end_date = self.today + timedelta(days=62)
        self.plan.save(update_fields=["planned_start_date", "planned_end_date"])

        check_and_notify_plans()

        self.assertEqual(Notification.objects.count(), 0)

    def test_reminder_is_idempotent_across_runs(self):
        check_and_notify_plans()
        check_and_notify_plans()

        self.assertEqual(
            Notification.objects.filter(event_type="plan.reminder").count(), 1
        )

    def test_follow_up_fires_an_in_app_notification(self):
        check_and_notify_plans()
        self.plan.planned_start_date = self.today + timedelta(days=10)
        self.plan.planned_end_date = self.today + timedelta(days=12)
        self.plan.save(update_fields=["planned_start_date", "planned_end_date"])
        self.plan.notified_at = timezone.now() - timedelta(days=FOLLOW_UP_AFTER_DAYS)
        self.plan.follow_up_sent_at = None
        self.plan.save(update_fields=["notified_at", "follow_up_sent_at"])

        check_and_notify_plans()

        row = Notification.objects.get(recipient=self.employee, event_type="plan.follow_up")
        self.assertIn("have not applied yet", row.message)
        self.assertEqual(row.link, f"/dashboard/plans/{self.plan.pk}")
