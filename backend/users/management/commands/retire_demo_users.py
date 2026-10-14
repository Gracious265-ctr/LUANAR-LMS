"""Retire the seeded demo accounts without touching their history.

``seed_dev_users`` creates seven people on ``@test.luanar`` with a published
password. That is right for a test fixture and wrong for a database anyone else
may point at: those accounts can sign in, and the addresses are undeliverable,
so every notification to them fails on SMTP.

They cannot simply be deleted, which is the more obvious answer. Roughly two
dozen foreign keys point at ``users.User`` with ``PROTECT`` — audit entries,
approval decisions, delegations and reassignments, approver role assignments,
section membership, balance transactions — so a demo account with any history
refuses to be deleted, by design. Deactivation gets what is actually wanted:

* the accounts stop authenticating (``ModelBackend`` refuses ``is_active=False``,
  and ``workflows.services.is_approver_user`` already excludes them, so no
  approval can route to a retired account);
* every application, decision and audit row stays exactly where it is;
* it is reversible with ``--undo``.

Idempotent: accounts already retired are skipped. Re-running ``seed_dev_users``
afterwards will not revive them, because its ``defaults`` do not mention
``is_active``.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from audit.models import AuditEntry
from audit.services import record_audit

User = get_user_model()

DEMO_EMAIL_DOMAIN = "test.luanar"
DEMO_PASSWORD = "testpass123"


class Command(BaseCommand):
    help = (
        "Deactivate the seeded @test.luanar demo accounts and strip their "
        "passwords, keeping every application, decision and audit row intact. "
        "Use --undo to reactivate them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--undo",
            action="store_true",
            help="Reactivate the demo accounts and restore the seeded password.",
        )

    def handle(self, *args, **options):
        undo = bool(options["undo"])
        demo_users = list(
            User.objects.filter(email__iendswith=f"@{DEMO_EMAIL_DOMAIN}").order_by("pk")
        )

        if not demo_users:
            self.stdout.write("No seeded demo accounts found; nothing to do.")
            return

        changed = 0
        for user in demo_users:
            changed += self._revive(user) if undo else self._retire(user)

        verb = "reactivated" if undo else "deactivated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo accounts {verb}: {changed} change(s) across "
                f"{len(demo_users)} account(s)."
            )
        )
        for user in demo_users:
            self.stdout.write(f"  - {user.username} ({user.get_full_name() or 'no name'})")

    def _retire(self, user) -> int:
        """Deactivate and strip the password; 1 when something actually changed."""
        changed = 0
        if user.is_active:
            user.is_active = False
            changed += 1
        if user.has_usable_password():
            user.set_unusable_password()
            changed += 1
        if changed:
            user.save(update_fields=["is_active", "password"])
            self._audit(user, AuditEntry.Action.DEACTIVATED)
        return changed

    def _revive(self, user) -> int:
        """Restore the seeded demo state; 1 per field that actually changed."""
        changed = 0
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
            self._audit(user, AuditEntry.Action.ACTIVATED)
            changed += 1
        if not user.has_usable_password():
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
            changed += 1
        return changed

    def _audit(self, user, action: str) -> None:
        """Record the change with no actor: a maintenance command, not a person."""
        record_audit(
            actor=None,
            action=action,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id=user.pk,
            target_summary=user.get_full_name() or user.email,
            detail={
                "source": "retire_demo_users",
                "reason": "seeded demo account retired",
            },
        )
