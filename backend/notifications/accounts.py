"""The password-set email (the account family's one message).

An HR-created employee has no password, so their first contact with the system is
this mail. It is the only message the outbox carries for an account rather than
for a business subject, because a login link has nothing to point at in
``leave``/``workflows``/``plans`` — and it is queued through the same
:func:`notifications.tasks.enqueue_delivery` as everything else, so it retries,
records ``sent``/``failed`` and honours the development recipient override.

Two rules are enforced here rather than left to callers:

* **Never put a live secret on a plain-HTTP link.** ``FRONTEND_URL`` is
  deployment configuration and nothing validates it, so outside ``DEBUG`` a
  non-HTTPS base refuses to compose at all. Failing the HR request is the correct
  outcome; mailing a password link over plain HTTP is not.
* **Never mail a link to nowhere.** An account with no email address, or a
  retired one, logs and returns rather than producing an undeliverable row.
"""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from notifications.models import NotificationOutbox

logger = logging.getLogger(__name__)

KIND_PASSWORD_SET = "password_set"
KIND_PASSWORD_CHANGED = "password_changed"
ROLE_ACCOUNT = "account"

_SUBJECT = "Set your LUANAR Leave password"
_BODY = """Hello {full_name},

HR has created your account for the LUANAR Leave Management System. Nobody has
set your password yet, and nobody will: you choose it yourself with the link
below.

{link}

This link works once and expires on {expires}. If it has expired, or the mail
never arrived, ask HR to send another one, or request one yourself from the
sign-in page.

If you were not expecting this message, ignore it and tell HR.

--
LUANAR Leave Management System
"""


def _set_password_link(secret: str) -> str:
    """The absolute link a person clicks, or a refusal to build one."""
    base = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if not base:
        raise ImproperlyConfigured(
            "FRONTEND_URL is not set, so a password-set link cannot be built. "
            "Set it to the absolute base URL of the web app (see .env.example)."
        )
    if not settings.DEBUG and not base.lower().startswith("https://"):
        raise ImproperlyConfigured(
            "FRONTEND_URL is not HTTPS, so a password-set link would hand a live "
            f"secret over plain HTTP. Configure an https:// URL for {base!r}."
        )
    return f"{base}/set-password?token={quote(secret, safe='')}"


def queue_password_set_email(*, user, secret: str, expires_at: datetime) -> None:
    """Record one password-set email and queue it for the account holder.

    A plain ``create`` rather than the ``get_or_create`` the event composers use:
    every issuance is a genuinely new message (a resend that matched an existing
    row would send nothing), and the single-use token — not a unique constraint —
    is what stops one link being used twice.
    """
    from notifications.tasks import enqueue_delivery

    recipient = str(getattr(user, "email", "") or "").strip()
    if not recipient:
        logger.warning(
            "Account %s has no email address, so no password-set link was queued. "
            "HR must add an address to the employee record first.",
            user.pk,
        )
        return

    link = _set_password_link(secret)

    row = NotificationOutbox.objects.create(
        user=user,
        kind=KIND_PASSWORD_SET,
        role_label=ROLE_ACCOUNT,
        recipient_email=recipient,
        subject=_SUBJECT,
        body=_BODY.format(
            full_name=user.get_full_name() or recipient,
            link=link,
            expires=expires_at.strftime("%d %B %Y at %H:%M UTC"),
        ),
    )

    enqueue_delivery(row, recipients=[recipient])


_CHANGED_SUBJECT = "Your LUANAR Leave password was changed"
_CHANGED_BODY = """Hello {full_name},

The password for your LUANAR Leave Management System account was changed on
{changed}.

Every signed-in session was ended, so you will need to sign in again.

If this was you, no action is needed beyond signing in. If it was not, tell HR
straight away: somebody had access to your account, and this message is the
evidence.

--
LUANAR Leave Management System
"""


def queue_password_changed_email(*, user) -> None:
    """Tell the account holder their password changed, whoever changed it.

    This is the notice that makes the change visible from the outside. The whole
    reason somebody changes a password they already know is that they suspect it
    is not private any more, so a silent password change is the change that
    helps an attacker most: they get a new password, they keep the account, and
    the owner finds out from a lockout rather than a message.

    Sent regardless of who made the change, because the interesting case is
    precisely the one where it was not the owner.
    """
    from notifications.tasks import enqueue_delivery

    recipient = str(getattr(user, "email", "") or "").strip()
    if not recipient:
        logger.warning(
            "Account %s has no email address, so no password-change notice was "
            "queued.",
            user.pk,
        )
        return

    changed_at = timezone.now()

    row = NotificationOutbox.objects.create(
        user=user,
        kind=KIND_PASSWORD_CHANGED,
        role_label=ROLE_ACCOUNT,
        recipient_email=recipient,
        subject=_CHANGED_SUBJECT,
        body=_CHANGED_BODY.format(
            full_name=user.get_full_name() or recipient,
            changed=changed_at.strftime("%d %B %Y at %H:%M UTC"),
        ),
    )

    enqueue_delivery(row, recipients=[recipient])
