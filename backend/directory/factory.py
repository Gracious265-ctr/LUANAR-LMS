"""Settings-driven factory for the organisation data provider."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .provider import OrganizationDataProvider


def get_organization_provider() -> OrganizationDataProvider:
    """Instantiate the provider named by ``ORG_DATA_BACKEND``.

    ``"fixture"`` is the placeholder implementation that ships with this unit.
    ``"api"`` is the reserved name for the real directory integration and
    raises deliberately until it exists — never a silent fallback, so a
    misconfigured deployment fails loudly instead of serving fixture data.
    """
    backend = settings.ORG_DATA_BACKEND
    if backend == "fixture":
        from .fixtures.provider import FixtureOrganizationDataProvider

        return FixtureOrganizationDataProvider()
    if backend == "api":
        raise ImproperlyConfigured(
            "ORG_DATA_BACKEND='api' is reserved for the real organisation "
            "directory integration, which has not shipped yet. Use 'fixture' "
            "until it does."
        )
    raise ImproperlyConfigured(
        f"Unknown ORG_DATA_BACKEND {backend!r}; expected 'fixture' (or 'api' "
        "once the real integration ships)."
    )
