"""Pull the organisation structure from the configured provider (unit 05).

Runs the sync behind one command so HR (or a deployment script) can refresh
the mirrored org tree without a shell. Idempotent: safe to re-run.
"""

from django.core.management.base import BaseCommand

from directory.factory import get_organization_provider
from org.services import sync_org_structure_from_provider


class Command(BaseCommand):
    help = (
        "Sync org units and role holders from the configured ORG_DATA_BACKEND "
        "provider into OrgUnit rows. Idempotent; re-running updates in place."
    )

    def handle(self, *args, **options):
        provider = get_organization_provider()
        summary = sync_org_structure_from_provider(provider)
        self.stdout.write(
            self.style.SUCCESS(
                "Org sync: {created} created, {updated} updated, "
                "{role_linked} role-linked, {vacant} vacant.".format(**summary)
            )
        )
