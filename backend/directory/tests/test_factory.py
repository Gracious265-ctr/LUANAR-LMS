"""``ORG_DATA_BACKEND`` selects the provider; "api" fails loudly, not softly."""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from directory.factory import get_organization_provider
from directory.fixtures.provider import FixtureOrganizationDataProvider


class OrganizationProviderFactoryTests(SimpleTestCase):
    def test_defaults_to_the_fixture_provider(self):
        self.assertIsInstance(
            get_organization_provider(), FixtureOrganizationDataProvider
        )

    @override_settings(ORG_DATA_BACKEND="fixture")
    def test_fixture_backend_returns_the_fixture_provider(self):
        self.assertIsInstance(
            get_organization_provider(), FixtureOrganizationDataProvider
        )

    @override_settings(ORG_DATA_BACKEND="api")
    def test_api_backend_raises_until_it_ships(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, "has not shipped yet"
        ):
            get_organization_provider()

    @override_settings(ORG_DATA_BACKEND="sso")
    def test_unknown_backend_raises_with_the_offending_value(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "'sso'"):
            get_organization_provider()
