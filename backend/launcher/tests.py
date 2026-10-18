from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from .services import can_access_leave_config, get_launcher_apps

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
