"""Services for this app: self-service passwords.

**Self-service passwords** (``request_password_set``,
``confirm_password_set``, ``change_password``). HR creates accounts and cannot
know a password, so without these a real employee had no path to sign in and
therefore no way to receive or act on any notification the system sends. The
properties that matter: no enumeration (a request answers identically whether
the address belongs to an active account or to nobody), one live link per
account, hash-only storage, and an audit entry for both halves.

One password-set link per account is enforced by invalidating the outstanding
ones rather than by a uniqueness constraint, because "used" and "superseded" are
different states and only the first of them is a consumption.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import record_audit

from .models import PasswordSetToken

logger = logging.getLogger(__name__)

User = get_user_model()

# 32 bytes of entropy from the OS CSPRNG, urlsafe-encoded for the link. 256 bits
# makes guessing a token infeasible; the throttles and the expiry are defence in
# depth around that, not the thing it relies on.
SECRET_BYTES = 32

GENERIC_REQUEST_RESPONSE = (
    "If that address has an account, a set-password link is on its way."
)


class WrongPasswordError(Exception):
    """Raised when the supplied current password does not match.

    Distinct from the validators' ``ValidationError`` on purpose: not knowing your
    own password is a different problem from picking a bad new one, and the two
    want different messages at the keyboard.
    """


class InvalidPasswordSetToken(Exception):
    """Raised when a presented token cannot set a password.

    One exception for every rejection reason — unknown, expired, already used,
    superseded or belonging to a deactivated account. Telling the caller which
    one it was would help nobody, since the legitimate holder cannot fix any of
    them except by asking HR for a fresh link.
    """


def hash_token(secret: str) -> str:
    """The value persisted for a secret: SHA-256, hex."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _link_lifetime() -> timedelta:
    hours = getattr(settings, "PASSWORD_SET_TOKEN_LIFETIME_HOURS", 72)
    return timedelta(hours=int(hours))


def _summary(user) -> str:
    return user.get_full_name() or user.email


def _lookup_user(email: str):
    """The active account for an address, or ``None``.

    Matched on ``email`` (what the form asks for) and, defensively, on
    ``username``, because seeded accounts store the address in both columns.
    """
    from django.db.models import Q

    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    return (
        User.objects.filter(Q(email__iexact=normalized) | Q(username__iexact=normalized))
        .order_by("pk")
        .first()
    )


def request_password_set(email: str, *, actor=None):
    """Issue and email a set-password link. Returns the token, or ``None``.

    ``actor`` is the HR user reissuing a link, or ``None`` when the person asked
    for it themselves. Returns ``None`` for an unknown, deactivated or
    address-less account — the caller must not turn that into a different answer
    for the requester.
    """
    from notifications.accounts import queue_password_set_email

    user = _lookup_user(email)
    if user is None or not user.is_active or not user.email:
        logger.info(
            "A set-password link was requested for an address with no usable "
            "active account; nothing was sent."
        )
        return None

    now = timezone.now()
    expires_at = now + _link_lifetime()
    secret = secrets.token_urlsafe(SECRET_BYTES)

    with transaction.atomic():
        # Supersede any outstanding link so only the newest one works.
        PasswordSetToken.objects.filter(
            user=user, used_at__isnull=True, invalidated_at__isnull=True
        ).update(invalidated_at=now)

        token = PasswordSetToken.objects.create(
            user=user,
            token_hash=hash_token(secret),
            expires_at=expires_at,
            issued_by=actor if getattr(actor, "pk", None) else None,
        )

        record_audit(
            actor=actor or user,
            action=AuditEntry.Action.PASSWORD_SET_REQUESTED,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id=user.pk,
            target_summary=_summary(user),
            detail={
                "expires_at": expires_at.isoformat(),
                "issued_by_hr": bool(getattr(actor, "pk", None)),
            },
        )

        # Writes the outbox row here; delivery is dispatched on commit.
        queue_password_set_email(user=user, secret=secret, expires_at=expires_at)

    logger.info("Issued a password-set link for account %s.", user.pk)
    return token


def token_is_usable(secret: str) -> bool:
    """Whether a token could still be used — for the page, before showing a form."""
    if not secret:
        return False
    token = PasswordSetToken.objects.select_related("user").filter(
        token_hash=hash_token(secret)
    ).first()
    return token is not None and token.is_usable()


def confirm_password_set(secret: str, password: str):
    """Set the password behind ``secret`` and return the user.

    Raises :class:`InvalidPasswordSetToken` for anything other than a live token,
    and ``django.core.exceptions.ValidationError`` when the password itself fails
    Django's configured validators — the two are different problems for the
    person at the keyboard, so they stay distinguishable here and are reported
    differently by the endpoint.
    """
    if not secret:
        raise InvalidPasswordSetToken()

    with transaction.atomic():
        token = (
            PasswordSetToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=hash_token(secret))
            .first()
        )
        if token is None or not token.is_usable():
            raise InvalidPasswordSetToken()

        user = token.user
        validate_password(password, user)

        now = timezone.now()
        user.set_password(password)
        user.save(update_fields=["password"])

        PasswordSetToken.objects.filter(
            user=user, used_at__isnull=True, invalidated_at__isnull=True
        ).update(used_at=now)

        record_audit(
            actor=user,
            action=AuditEntry.Action.PASSWORD_SET,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id=user.pk,
            target_summary=_summary(user),
            detail={"self_service": True},
        )

    logger.info("Account %s set its password.", user.pk)
    return user


def change_password(*, user, current_password: str, new_password: str) -> None:
    """Set a new password for a signed-in user and sign every session out.

    Doing this from a live session rather than an emailed link changes what has
    to be checked. There is no token to prove anything, so the current password
    is the proof: without it, anyone holding a borrowed or observed access token
    could rotate the account's password and lock the real owner out of their own
    leave history permanently. That is the reason this endpoint re-authenticates
    even though the caller is already authenticated.

    Raises :class:`WrongPasswordError` when the current password is wrong, and
    ``django.core.exceptions.ValidationError`` when the new one fails Django's
    configured validators.
    """
    from notifications.accounts import queue_password_changed_email

    if not user.check_password(current_password):
        # Deliberately not audited as a PASSWORD_CHANGED: nothing changed. The
        # throttle is what makes guessing expensive; a failed attempt that also
        # cannot be distinguished from a typo is better as a log line than as a
        # row in the append-only audit trail.
        logger.warning(
            "A password change for account %s supplied the wrong current "
            "password.",
            user.pk,
        )
        raise WrongPasswordError()

    if user.check_password(new_password):
        # Not covered by AUTH_PASSWORD_VALIDATORS: Django's
        # UserAttributeSimilarityValidator compares username/name/email and
        # never the current password, so "change" to the same value would
        # otherwise succeed and stamp a fresh watermark for nothing.
        raise DjangoValidationError(
            "Your new password must be different from your current password."
        )

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        validate_password(new_password, locked)

        now = timezone.now()
        locked.set_password(new_password)
        locked.save(update_fields=["password"])

        # A set-password link that was mailed before this change must not survive
        # it. Otherwise somebody holding that link could reset the password again
        # after the owner has deliberately moved on from it.
        PasswordSetToken.objects.filter(
            user=locked, used_at__isnull=True, invalidated_at__isnull=True
        ).update(invalidated_at=now)

        record_audit(
            actor=user,
            action=AuditEntry.Action.PASSWORD_CHANGED,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
            target_id=locked.pk,
            target_summary=_summary(locked),
            detail={"self_service": True},
        )

        # The mail is the point at which somebody else changing this password
        # becomes visible to its owner. Queued like every other message, and
        # deliberately not gated on having sent this password: it goes to the
        # address on file regardless of who made the change.
        queue_password_changed_email(user=locked)

    logger.info("Account %s changed its password; other sessions signed out.", user.pk)
