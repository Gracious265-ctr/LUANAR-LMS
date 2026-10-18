"""Launcher aggregator — role gating and badge assembly.

The launcher owns no access rules; it asks each module (``can_access_*``) and
reports the badge that module computes. These tests pin the *resulting* app set
per role — employee, approver, HR, superuser — and that a module's badge flows
through untouched (including the ``None`` case, which the frontend renders as no
badge rather than a "0").
"""

from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from leave.tests.stubs import make_user
from organisation.services import create_team_role_assignment
from users.models import User
from workflows.testing import (
    create_user_with_role,
    ensure_roles,
    make_employee,
    make_team,
)

from .services import get_launcher_apps

LAUNCHER_URL = reverse("launcher-apps")


def _keys(apps):
    return {app["key"] for app in apps}


class LauncherEndpointTests(APITestCase):
    def _apps_for(self, user):
        self.client.force_authenticate(user=user)
        response = self.client.get(LAUNCHER_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["apps"]

    def test_requires_authentication(self):
        response = APIClient().get(LAUNCHER_URL)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_employee_sees_only_self_service_apps(self):
        employee = make_user("emp@launcher", role=User.Role.EMPLOYEE)

        self.assertEqual(_keys(self._apps_for(employee)), {"leave", "documents"})

    def test_approver_sees_the_approvals_desk(self):
        approver = make_user("ap@launcher", role="hod")

        self.assertEqual(
            _keys(self._apps_for(approver)), {"leave", "approvals", "documents"}
        )

    def test_a_designated_team_manager_reaches_their_team(self):
        """The team a manager may configure lives inside Organisation.

        A designated manager is an ordinary employee account, so without the
        launcher offering the module there is no way for them to reach the roster
        and approval chains only they may write. They are not HR, so the
        administration app stays out of it. The approvals desk is theirs because
        a manager holds a real approver role on the team, not because they are a
        manager.
        """
        manager = make_employee("manager@launcher", team=None)
        team = make_team("Managed team", ["hod"])
        create_team_role_assignment(
            team=team,
            role=ensure_roles("dvc")["dvc"],
            user=manager,
            actor=make_user("hr@launcher", role=User.Role.HR),
            is_team_manager=True,
        )

        self.assertEqual(
            _keys(self._apps_for(manager)),
            {"leave", "approvals", "documents", "organisation"},
        )

    def test_hr_sees_administration_and_oversight(self):
        hr = make_user("hr@launcher", role=User.Role.HR)

        self.assertEqual(
            _keys(self._apps_for(hr)),
            {"leave", "approvals", "organisation", "documents", "hr-admin"},
        )

    def test_superuser_sees_administration_but_not_the_approvals_desk(self):
        # Superuser is system access, not a place in an approval chain: without
        # an approver role holding they have nothing to decide.
        root = create_user_with_role(
            "root@launcher",
            role=User.Role.EMPLOYEE,
            is_superuser=True,
            is_staff=True,
        )

        self.assertEqual(
            _keys(self._apps_for(root)),
            {"leave", "documents", "organisation", "hr-admin"},
        )


class LauncherBadgeTests(APITestCase):
    def test_approvals_badge_reports_the_pending_count(self):
        approver = make_user("ap@launcher", role="hod")
        self.client.force_authenticate(user=approver)

        with mock.patch(
            "launcher.services.pending_stage_count_for", return_value=3
        ):
            response = self.client.get(LAUNCHER_URL)

        apps = {app["key"]: app for app in response.data["apps"]}
        self.assertEqual(
            apps["approvals"]["badge"],
            {"count": 3, "label": "pending", "tone": "amber"},
        )

    def test_approvals_badge_is_none_when_nothing_is_pending(self):
        approver = make_user("ap@launcher", role="hod")
        self.client.force_authenticate(user=approver)

        with mock.patch(
            "launcher.services.pending_stage_count_for", return_value=0
        ):
            response = self.client.get(LAUNCHER_URL)

        apps = {app["key"]: app for app in response.data["apps"]}
        # No badge means the frontend renders nothing, never a "0".
        self.assertIsNone(apps["approvals"]["badge"])


class LauncherServiceTests(APITestCase):
    def test_get_launcher_apps_gates_anonymous(self):
        self.assertEqual(get_launcher_apps(None), [])
