from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from workflows.testing import ensure_roles, team_for

from .services import (
    can_access_documents,
    can_access_leave_config,
    can_access_org,
    get_launcher_apps,
)

User = get_user_model()


def make_user(role: str, email: str) -> User:
    return User.objects.create_user(
        username=email,
        email=email,
        password="hunter2-hunter2",
        first_name="Launcher",
        last_name="Test",
        role=role,
    )


class LeaveConfigLauncherTests(TestCase):
    """Spec 4.6: the card only appears for the accounts that can use it.

    The launcher is the first surface of the module, so it is where "is this
    HR-only?" is decided in public. A card that links to a page which then
    bounces the visitor back to the dashboard is worse than no card.
    """

    @staticmethod
    def keys(user) -> list[str]:
        return [app["key"] for app in get_launcher_apps(user)]

    def test_employee_never_sees_the_card(self):
        employee = make_user(User.Role.EMPLOYEE, "employee@example.com")
        self.assertNotIn("leave-config", self.keys(employee))

    def test_approver_never_sees_the_card(self):
        approver = make_user(User.Role.APPROVER, "approver@example.com")
        self.assertNotIn("leave-config", self.keys(approver))

    def test_hr_sees_the_card(self):
        hr = make_user(User.Role.HR, "hr@example.com")
        self.assertIn("leave-config", self.keys(hr))

    def test_superuser_sees_the_card(self):
        admin = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="hunter2-hunter2",
        )
        self.assertIn("leave-config", self.keys(admin))

    def test_the_card_carries_no_badge(self):
        # Configurability is a yes/no fact, not a quantity; a "0" badge would
        # read as "you have nothing to do", which is the opposite of what a
        # registry page full of leave types means.
        hr = make_user(User.Role.HR, "hr-badge@example.com")
        card = next(
            app for app in get_launcher_apps(hr) if app["key"] == "leave-config"
        )
        self.assertIsNone(card["badge"])

    def test_the_gate_matches_the_service_the_pages_use(self):
        hr = make_user(User.Role.HR, "hr-gate@example.com")
        employee = make_user(User.Role.EMPLOYEE, "employee-gate@example.com")
        from leave_config.services import can_access_leave_config as service_gate

        self.assertTrue(can_access_leave_config(hr))
        self.assertTrue(service_gate(hr))
        self.assertFalse(can_access_leave_config(employee))
        self.assertFalse(service_gate(employee))
        self.assertFalse(can_access_leave_config(AnonymousUser()))
        self.assertFalse(can_access_leave_config(None))


class OrgLauncherTests(TestCase):
    """The Workflows card is offered to HR, staff, and designated team managers.

    A team manager is an ordinary ``employee`` account whose only claim to the
    module is a team they manage, so the card is the one place the launcher has
    to look past ``User.role``. A card that appeared for them but bounced on the
    next page — or, worse, that never appeared at all — would leave the only
    person who can configure a team unable to reach it.
    """

    @staticmethod
    def keys(user) -> list[str]:
        return [app["key"] for app in get_launcher_apps(user)]

    def make_team_manager(self, email: str, *, role_code="supervisor", active=True):
        team = team_for(f"Team {email}")
        role = ensure_roles(role_code)[role_code]
        if not active:
            role.is_active = False
            role.save(update_fields=["is_active"])
        from teams.models import TeamRoleAssignment

        user = make_user(User.Role.EMPLOYEE, email)
        TeamRoleAssignment.objects.create(
            team=team, role=role, user=user, is_team_manager=True
        )
        return user, team

    def test_hr_sees_the_card(self):
        hr = make_user(User.Role.HR, "hr-org@example.com")
        self.assertIn("org", self.keys(hr))

    def test_superuser_sees_the_card(self):
        admin = User.objects.create_superuser(
            username="admin-org@example.com",
            email="admin-org@example.com",
            password="hunter2-hunter2",
        )
        self.assertIn("org", self.keys(admin))

    def test_team_manager_sees_the_card(self):
        manager, _ = self.make_team_manager("manager-org@example.com")
        self.assertIn("org", self.keys(manager))

    def test_ordinary_employee_never_sees_the_card(self):
        employee = make_user(User.Role.EMPLOYEE, "plain-org@example.com")
        self.assertNotIn("org", self.keys(employee))

    def test_retiring_the_role_closes_the_door(self):
        # A manager's authority is the *active* role they hold; deactivating it
        # must take the card with it, or the launcher would promise a module the
        # per-page guard then refuses.
        manager, _ = self.make_team_manager(
            "retired-org@example.com", active=False
        )
        self.assertNotIn("org", self.keys(manager))

    def test_the_gate_matches_the_page_guard(self):
        manager, _ = self.make_team_manager("guard-org@example.com")
        employee = make_user(User.Role.EMPLOYEE, "guard-plain@example.com")
        from organisation.services import managed_team_ids_for

        self.assertTrue(can_access_org(manager))
        self.assertEqual(len(managed_team_ids_for(manager)), 1)
        self.assertFalse(can_access_org(employee))
        self.assertEqual(managed_team_ids_for(employee), [])
        self.assertFalse(can_access_org(AnonymousUser()))
        self.assertFalse(can_access_org(None))


class DocumentsLauncherTests(TestCase):
    """Documents is every account's filing cabinet, so the card is everyone's.

    Scoping happens per row at the list endpoints, not on the launcher, so the
    only question here is whether a signed-in account may open the module at
    all — and whether a signed-out one may not.
    """

    @staticmethod
    def keys(user) -> list[str]:
        return [app["key"] for app in get_launcher_apps(user)]

    def test_every_role_sees_the_card(self):
        for role, email in [
            (User.Role.EMPLOYEE, "employee-docs@example.com"),
            (User.Role.APPROVER, "approver-docs@example.com"),
            (User.Role.HR, "hr-docs@example.com"),
        ]:
            with self.subTest(role=role):
                self.assertIn("documents", self.keys(make_user(role, email)))

    def test_a_superuser_sees_the_card(self):
        admin = User.objects.create_superuser(
            username="admin-docs@example.com",
            email="admin-docs@example.com",
            password="hunter2-hunter2",
        )
        self.assertIn("documents", self.keys(admin))

    def test_a_team_manager_sees_the_card(self):
        team = team_for("Documents Team")
        role = ensure_roles("supervisor")["supervisor"]
        from teams.models import TeamRoleAssignment

        manager = make_user(User.Role.EMPLOYEE, "manager-docs@example.com")
        TeamRoleAssignment.objects.create(
            team=team, role=role, user=manager, is_team_manager=True
        )
        self.assertIn("documents", self.keys(manager))

    def test_the_gate_is_signed_in_or_not(self):
        employee = make_user(User.Role.EMPLOYEE, "gate-docs@example.com")
        self.assertTrue(can_access_documents(employee))
        self.assertFalse(can_access_documents(AnonymousUser()))
        self.assertFalse(can_access_documents(None))

