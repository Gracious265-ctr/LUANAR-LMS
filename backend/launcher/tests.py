from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from chains.testing import ensure_roles, team_for

from .services import (
    can_access_calendar,
    can_access_documents,
    can_access_leave_types,
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


class LauncherKeyContractTests(TestCase):
    """The keys the launcher emits are a contract with the frontend registry.

    ``frontend/lib/apps-registry.ts`` turns each key into a card, and
    ``AppLauncherGrid`` drops a key it does not recognise without a trace — so a
    renamed module costs its card for every entitled role and nothing fails.
    That is exactly what happened when the apps were restructured: the backend
    kept emitting ``org`` and ``leave-types`` while the registry had moved to
    ``teams`` and ``leave-config``, and HR silently lost both cards.

    HR is the role that is entitled to every card, so its set is the whole
    contract. Adding, renaming, or removing a card must update the registry in
    the same commit — this test is the reminder.
    """

    # Keep in step with APPS_REGISTRY in frontend/lib/apps-registry.ts.
    EXPECTED_KEYS = {
        "leave",
        "plans",
        "approvals",
        "teams",
        "documents",
        "leave-config",
        "calendar-app",
    }

    def test_hr_card_keys_are_the_ones_the_frontend_registry_defines(self):
        hr = make_user(User.Role.HR, "contract-hr@example.com")
        keys = {app["key"] for app in get_launcher_apps(hr)}
        self.assertEqual(keys, self.EXPECTED_KEYS)

    def test_no_card_is_emitted_that_the_contract_does_not_name(self):
        # One card per module: an unknown key here is a card nobody can see.
        for role, email in [
            (User.Role.EMPLOYEE, "contract-employee@example.com"),
            (User.Role.APPROVER, "contract-approver@example.com"),
            (User.Role.HR, "contract-hr-all@example.com"),
        ]:
            with self.subTest(role=role):
                emitted = {app["key"] for app in get_launcher_apps(make_user(role, email))}
                self.assertLessEqual(emitted, self.EXPECTED_KEYS)


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
        from leave_types.services import can_access_leave_types as service_gate

        self.assertTrue(can_access_leave_types(hr))
        self.assertTrue(service_gate(hr))
        self.assertFalse(can_access_leave_types(employee))
        self.assertFalse(service_gate(employee))
        self.assertFalse(can_access_leave_types(AnonymousUser()))
        self.assertFalse(can_access_leave_types(None))


class CalendarLauncherTests(TestCase):
    """Refinement unit 07 §2: the Calendar card is HR/superuser only."""

    @staticmethod
    def keys(user) -> list[str]:
        return [app["key"] for app in get_launcher_apps(user)]

    def test_employee_never_sees_the_card(self):
        employee = make_user(User.Role.EMPLOYEE, "cal-employee@example.com")
        self.assertNotIn("calendar-app", self.keys(employee))

    def test_hr_sees_the_card(self):
        hr = make_user(User.Role.HR, "cal-hr@example.com")
        self.assertIn("calendar-app", self.keys(hr))

    def test_superuser_sees_the_card(self):
        admin = User.objects.create_superuser(
            username="cal-admin@example.com",
            email="cal-admin@example.com",
            password="hunter2-hunter2",
        )
        self.assertIn("calendar-app", self.keys(admin))

    def test_the_gate_matches_the_calendar_service(self):
        from calendar_app.services import can_access_calendar as service_gate

        hr = make_user(User.Role.HR, "cal-gate-hr@example.com")
        employee = make_user(User.Role.EMPLOYEE, "cal-gate-emp@example.com")

        self.assertTrue(can_access_calendar(hr))
        self.assertTrue(service_gate(hr))
        self.assertFalse(can_access_calendar(employee))
        self.assertFalse(can_access_calendar(None))


class TeamsLauncherTests(TestCase):
    """The Teams card is offered to HR, staff, and designated team managers.

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
        self.assertIn("teams", self.keys(hr))

    def test_superuser_sees_the_card(self):
        admin = User.objects.create_superuser(
            username="admin-org@example.com",
            email="admin-org@example.com",
            password="hunter2-hunter2",
        )
        self.assertIn("teams", self.keys(admin))

    def test_team_manager_sees_the_card(self):
        manager, _ = self.make_team_manager("manager-org@example.com")
        self.assertIn("teams", self.keys(manager))

    def test_ordinary_employee_never_sees_the_card(self):
        employee = make_user(User.Role.EMPLOYEE, "plain-org@example.com")
        self.assertNotIn("teams", self.keys(employee))

    def test_retiring_the_role_closes_the_door(self):
        # A manager's authority is the *active* role they hold; deactivating it
        # must take the card with it, or the launcher would promise a module the
        # per-page guard then refuses.
        manager, _ = self.make_team_manager(
            "retired-org@example.com", active=False
        )
        self.assertNotIn("teams", self.keys(manager))

    def test_the_gate_matches_the_page_guard(self):
        manager, _ = self.make_team_manager("guard-org@example.com")
        employee = make_user(User.Role.EMPLOYEE, "guard-plain@example.com")
        from roles.services import managed_team_ids_for

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

