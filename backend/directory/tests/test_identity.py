"""Email-based reconciliation between local users and provider employees."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from directory.services import (
    find_provider_employee_for_user,
    get_local_user_for_external_employee,
)

User = get_user_model()

#: A fixture employee that exists in directory/fixtures/seed_data.json.
KNOWN_EMPLOYEE_ID = "EMP-003"
KNOWN_EMAIL = "registrar@test.luanar"


class FindProviderEmployeeTests(TestCase):
    def test_resolves_a_user_by_email(self):
        user = User.objects.create_user(
            username=KNOWN_EMAIL, email=KNOWN_EMAIL, password="pass"
        )

        record = find_provider_employee_for_user(user)

        self.assertIsNotNone(record)
        self.assertEqual(record.email, KNOWN_EMAIL)

    def test_match_is_case_insensitive(self):
        user = User.objects.create_user(
            username="cased", email=KNOWN_EMAIL.upper(), password="pass"
        )

        self.assertIsNotNone(find_provider_employee_for_user(user))

    def test_unknown_email_returns_none(self):
        user = User.objects.create_user(
            username="stranger@luanar", email="stranger@luanar", password="pass"
        )

        self.assertIsNone(find_provider_employee_for_user(user))

    def test_user_without_an_email_returns_none(self):
        user = User.objects.create_user(username="no-email", password="pass")

        self.assertIsNone(find_provider_employee_for_user(user))


class LocalUserForExternalEmployeeTests(TestCase):
    def test_resolves_the_seeded_employee_to_a_local_user(self):
        user = User.objects.create_user(
            username=KNOWN_EMAIL, email=KNOWN_EMAIL, password="pass"
        )

        self.assertEqual(
            get_local_user_for_external_employee(KNOWN_EMPLOYEE_ID), user
        )

    def test_lookup_is_case_insensitive_on_the_email(self):
        user = User.objects.create_user(
            username="cased", email=KNOWN_EMAIL.upper(), password="pass"
        )

        self.assertEqual(
            get_local_user_for_external_employee(KNOWN_EMPLOYEE_ID), user
        )

    def test_unknown_employee_id_returns_none(self):
        self.assertIsNone(
            get_local_user_for_external_employee("does-not-exist")
        )

    def test_blank_employee_id_returns_none(self):
        self.assertIsNone(get_local_user_for_external_employee(""))
        self.assertIsNone(get_local_user_for_external_employee(None))

    def test_employee_without_a_local_user_returns_none(self):
        self.assertIsNone(get_local_user_for_external_employee(KNOWN_EMPLOYEE_ID))
