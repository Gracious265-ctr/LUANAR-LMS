"""Tests for the system-admin dashboard.

The suite pins the two decisions that shape this surface: the site is mounted at
``/system-admin/`` (not the stock ``/admin/``), and there is no HR tier — only
superusers see dashboard additions, while every other staff account (HR
included) sees the stock admin index. It also covers the three
account-management actions, the confirmation flow, and the health checks.
"""

from datetime import timedelta
from unittest import mock

from django.contrib import admin
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEntry
from django_q.models import Failure, OrmQ, Success
from leave.models import LeaveApplication, SupportingDocument
from users.admin import UserAdmin
from users.models import User
from approvals.models import ApplicationStage

from .actions import grant_staff_access, grant_superuser, revoke_superuser
from .health import (
    _check_database,
    _check_storage,
    _check_task_runner,
    gather_health_status,
)
from .services import (
    ADMIN_ACTION_EVENTS,
    gather_dashboard_stats,
    get_dashboard_tier,
    get_recent_admin_actions,
)

ADMIN_INDEX = "/system-admin/"
USER_CHANGELIST = "/system-admin/users/user/"


def make_user(username="user@example.com", **kwargs):
    return User.objects.create_user(
        username=username, email=username, password="pw", **kwargs
    )


def make_superuser(username="root@example.com"):
    return User.objects.create_superuser(
        username=username, email=username, password="pw"
    )


def make_task(success=True, *, stopped=None, task_id=None):
    now = stopped or timezone.now()
    model = Success if success else Failure
    return model.objects.create(
        id=(task_id or "a" * 32),
        name="test-task",
        func="tests.noop",
        started=now,
        stopped=now,
    )


class DashboardTierTests(TestCase):
    def test_superuser_gets_superuser_tier(self):
        self.assertEqual(get_dashboard_tier(make_superuser()), "superuser")

    def test_ordinary_staff_get_plain_tier(self):
        user = make_user(is_staff=True)
        self.assertEqual(get_dashboard_tier(user), "plain")

    def test_hr_accounts_get_plain_tier(self):
        """HR is an end-user of the product, not a dashboard tier."""
        hr = make_user(username="hr@example.com", is_staff=True, role=User.Role.HR)
        hr.groups.create(name="HR")
        hr = User.objects.get(pk=hr.pk)
        self.assertEqual(get_dashboard_tier(hr), "plain")

    def test_anonymous_is_plain_tier(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(get_dashboard_tier(AnonymousUser()), "plain")


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.employee = make_user()
        self.application = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        ApplicationStage.objects.create(
            application=self.application,
            stage_order=1,
            role="supervisor",
            role_label="Supervisor",
            status=ApplicationStage.Status.PENDING,
        )
        SupportingDocument.objects.create(
            application=self.application,
            file_path="leave-documents/x/a.pdf",
            file_url="https://example.com/a.pdf",
            file_name="a.pdf",
            file_size=2048,
            content_type="application/pdf",
        )

    def test_stats_shape_and_values(self):
        stats = gather_dashboard_stats()
        self.assertEqual(
            set(stats),
            {
                "users_total",
                "users_active_30d",
                "applications",
                "pending_approvals",
                "documents",
                "tasks",
                "database",
            },
        )
        apps = stats["applications"]
        self.assertEqual(apps["total"], 1)
        self.assertEqual(apps["pending"], 1)
        self.assertEqual(apps["submitted_today"], 1)
        self.assertEqual(apps["submitted_this_week"], 1)
        self.assertEqual(stats["pending_approvals"], 1)
        self.assertEqual(stats["documents"]["active"], 1)
        self.assertEqual(stats["documents"]["storage_bytes"], 2048)
        self.assertIsNotNone(stats["database"])

    def test_single_stat_degrades_independently(self):
        with mock.patch("system_admin.services.LeaveApplication") as patched:
            patched.objects.count.side_effect = RuntimeError("boom")
            stats = gather_dashboard_stats()
        self.assertIsNone(stats["applications"])
        # The rest of the dashboard is unaffected.
        self.assertEqual(stats["documents"]["active"], 1)
        self.assertIsNotNone(stats["database"])

    def test_pending_approvals_excludes_non_pending(self):
        self.application.stages.update(status=ApplicationStage.Status.APPROVED)
        self.assertEqual(gather_dashboard_stats()["pending_approvals"], 0)


class RecentAdminActionsTests(TestCase):
    def test_only_system_actions_are_returned_newest_first(self):
        actor = make_superuser()
        AuditEntry.objects.create(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.RECORD,
            target_id="1",
            target_summary="noise",
        )
        first = AuditEntry.objects.create(
            actor=actor,
            action=AuditEntry.Action.SYSTEM_STAFF_ACCESS_GRANTED,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id="1",
            target_summary="older",
        )
        second = AuditEntry.objects.create(
            actor=actor,
            action=AuditEntry.Action.SYSTEM_SUPERUSER_GRANTED,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id="2",
            target_summary="newer",
        )
        entries = get_recent_admin_actions()
        self.assertEqual([e.pk for e in entries], [second.pk, first.pk])
        self.assertTrue(all(e.action in ADMIN_ACTION_EVENTS for e in entries))


class DashboardAccessTests(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(ADMIN_INDEX)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/system-admin/login/", response["Location"])

    def test_non_staff_cannot_reach_the_site(self):
        self.client.force_login(make_user())
        response = self.client.get(ADMIN_INDEX)
        self.assertIn(response.status_code, (302, 403))

    def test_plain_staff_see_stock_admin_without_dashboard_context(self):
        self.client.force_login(make_user(is_staff=True))
        response = self.client.get(ADMIN_INDEX)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("stats", response.context)
        self.assertNotIn("health", response.context)
        self.assertNotIn("recent_admin_actions", response.context)

    def test_superuser_sees_dashboard_context(self):
        self.client.force_login(make_superuser())
        response = self.client.get(ADMIN_INDEX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_tier"], "superuser")
        self.assertIn("stats", response.context)
        self.assertIn("health", response.context)
        self.assertIn("recent_admin_actions", response.context)
        self.assertContains(response, "Leave applications")
        self.assertContains(response, "System health")

    def test_site_serves_under_system_admin_prefix(self):
        self.client.force_login(make_superuser())
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)


class HealthCheckUnitTests(TestCase):
    def test_database_is_ok(self):
        result = _check_database()
        self.assertEqual(result["status"], "ok")
        self.assertIn("latency_ms", result)

    def test_task_runner_unknown_without_history(self):
        self.assertEqual(_check_task_runner()["status"], "unknown")

    def test_task_runner_ok_when_recent(self):
        make_task(stopped=timezone.now())
        self.assertEqual(_check_task_runner()["status"], "ok")

    def test_task_runner_degraded_when_stale(self):
        make_task(stopped=timezone.now() - timedelta(hours=3))
        self.assertEqual(_check_task_runner()["status"], "degraded")

    def test_storage_down_when_unconfigured(self):
        self.assertEqual(_check_storage()["status"], "down")

    def test_storage_ok_when_ping_succeeds(self):
        with mock.patch("system_admin.health.ping_storage"):
            self.assertEqual(_check_storage()["status"], "ok")

    def test_gather_health_status_shape(self):
        health = gather_health_status()
        self.assertEqual(set(health), {"database", "tasks", "storage"})


class HealthViewTests(TestCase):
    def test_superuser_can_open_health_page(self):
        self.client.force_login(make_superuser())
        response = self.client.get(reverse("admin:system-health"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System health")

    def test_plain_staff_cannot_open_health_page(self):
        self.client.force_login(make_user(is_staff=True))
        response = self.client.get(reverse("admin:system-health"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_redirected(self):
        response = self.client.get(reverse("admin:system-health"))
        self.assertEqual(response.status_code, 302)

    def test_test_email_get_is_rejected(self):
        self.client.force_login(make_superuser())
        response = self.client.get(reverse("admin:system-test-email"))
        self.assertEqual(response.status_code, 405)

    def test_test_email_post_sends_to_caller(self):
        self.client.force_login(make_superuser())
        response = self.client.post(reverse("admin:system-test-email"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["root@example.com"])

    def test_test_email_post_requires_superuser(self):
        self.client.force_login(make_user(is_staff=True))
        response = self.client.post(reverse("admin:system-test-email"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)


class AccountActionTests(TestCase):
    def setUp(self):
        self.superuser = make_superuser()
        self.target = make_user(username="target@example.com")
        self.modeladmin = UserAdmin(User, admin.site)
        self.client.force_login(self.superuser)

    def _post_action(self, action, users):
        return self.client.post(
            USER_CHANGELIST,
            {
                "action": action,
                "_selected_action": [str(u.pk) for u in users],
            },
        )

    def _confirm(self, action, user):
        return self.client.post(
            USER_CHANGELIST,
            {
                "action": action,
                "_selected_action": [str(user.pk)],
                "confirm_username": user.username,
            },
        )

    def test_grant_requires_confirmation(self):
        response = self._post_action("grant_superuser", [self.target])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "confirm_username")
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_superuser)

    def test_grant_applies_and_audits(self):
        response = self._confirm("grant_superuser", self.target)
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_superuser)
        self.assertTrue(self.target.is_staff)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.SYSTEM_SUPERUSER_GRANTED,
                target_id=str(self.target.pk),
            ).exists()
        )

    def test_grant_rejects_mismatched_username(self):
        response = self.client.post(
            USER_CHANGELIST,
            {
                "action": "grant_superuser",
                "_selected_action": [str(self.target.pk)],
                "confirm_username": "not-the-username",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_superuser)
        self.assertFalse(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.SYSTEM_SUPERUSER_GRANTED
            ).exists()
        )

    def test_grant_requires_exactly_one_account(self):
        other = make_user(username="other@example.com")
        response = self._post_action("grant_superuser", [self.target, other])
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.target.is_superuser)
        self.assertFalse(other.is_superuser)

    def test_revoke_applies_and_audits(self):
        victim = make_superuser(username="victim@example.com")
        response = self._confirm("revoke_superuser", victim)
        self.assertEqual(response.status_code, 302)
        victim.refresh_from_db()
        self.assertFalse(victim.is_superuser)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.SYSTEM_SUPERUSER_REVOKED
            ).exists()
        )

    def test_cannot_revoke_own_superuser_status(self):
        response = self._confirm("revoke_superuser", self.superuser)
        self.assertEqual(response.status_code, 302)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_superuser)

    def test_grant_staff_access_applies_and_audits(self):
        response = self._confirm("grant_staff_access", self.target)
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_staff)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.SYSTEM_STAFF_ACCESS_GRANTED
            ).exists()
        )

    def test_actions_are_hidden_from_non_superusers(self):
        hr = make_user(
            username="hr@example.com",
            is_staff=True,
            role=User.Role.HR,
        )
        request = RequestFactory().get(USER_CHANGELIST)
        request.user = hr
        actions = self.modeladmin.get_actions(request)
        self.assertNotIn("grant_superuser", actions)
        self.assertNotIn("revoke_superuser", actions)
        self.assertNotIn("grant_staff_access", actions)

    def test_direct_call_by_non_superuser_is_refused(self):
        hr = make_user(
            username="hr2@example.com",
            is_staff=True,
            role=User.Role.HR,
        )
        request = RequestFactory().post(USER_CHANGELIST)
        request.user = hr
        queryset = User.objects.filter(pk=self.target.pk)
        for action in (grant_superuser, revoke_superuser, grant_staff_access):
            with self.subTest(action=action.__name__):
                with self.assertRaises(PermissionDenied):
                    action(self.modeladmin, request, queryset)
