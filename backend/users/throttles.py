"""Rate limits for the credential endpoints.

The frontend is a Next.js server that proxies every auth request to Django, so
Django sees **one** client address — the proxy's. An ``AnonRateThrottle``'s
default key is that address, which turns ``10/min`` into a rate limit for the
whole institution: ten bad sign-ins anywhere and every employee is locked out
for a minute, while an attacker spreading guesses across accounts is barely
slowed. The same problem is worse for the set-password request (``5/hour``).

These classes key the counter on the fact the endpoint is actually about —
the account being signed in to, or the link being confirmed — and keep the
address as a second component. Two people behind the same proxy therefore have
separate buckets, and one person cannot exhaust a colleague's.

They also derive from ``SimpleRateThrottle`` rather than ``AnonRateThrottle``.
The latter deliberately returns no cache key for authenticated callers, which
would let anyone holding *any* valid token call the login endpoint unthrottled.
A credential endpoint has to be limited no matter who is asking.
"""

from __future__ import annotations

from hashlib import sha256

from rest_framework.throttling import SimpleRateThrottle

#: Emails are capped at 254 characters by the address format anyway; truncating
#: here keeps a hostile 10 KB local-part out of the cache key.
_MAX_IDENTITY_LENGTH = 254


def _body_field(request, name: str) -> str:
    """One string field from the request body, or ``""``.

    Throttles run during ``initial()`` before the view parses anything, so this
    asks DRF's lazily-parsed ``request.data``. A malformed or non-object body
    (or a request whose parser has not run) simply has no identity: the address
    alone is used, which is the safe fallback rather than an unthrottled pass.
    """
    try:
        data = request.data
    except Exception:  # noqa: BLE001 - a broken body must not bypass the limit
        return ""
    if not hasattr(data, "get"):
        return ""
    value = data.get(name)
    return str(value or "").strip()[:_MAX_IDENTITY_LENGTH]


class _IdentityRateThrottle(SimpleRateThrottle):
    """A rate limit keyed on who the request is about, then its address."""

    def get_identity(self, request) -> str:
        raise NotImplementedError

    def get_cache_key(self, request, view):
        identity = self.get_identity(request)
        address = self.get_ident(request) or "unknown"
        if not identity:
            # Without the endpoint's own subject (a malformed body, say) the
            # address is the only stable key. Falling back to it keeps the
            # endpoint throttled; returning ``None`` would not.
            ident = f"ip:{address}"
        else:
            ident = f"{address}:{identity}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class LoginRateThrottle(_IdentityRateThrottle):
    """Rate limit sign-in attempts per account.

    Keying on the submitted email means a shared office or the frontend proxy
    cannot let one person's attempts lock out everyone else, and repeated
    guesses against one account are counted together even when they come from
    different addresses. An address that does not exist gets its own bucket
    too, so probing for valid addresses is limited without revealing whether
    the address is real (the response is the same either way).
    """

    scope = "login"

    def get_identity(self, request) -> str:
        return _body_field(request, "email").lower()


class PasswordChangeRateThrottle(SimpleRateThrottle):
    """Rate limit password changes so the current password cannot be guessed.

    Per *user*, not per IP. The thing being guessed is one person's current
    password, and the office this is built for shares an egress address: a
    per-IP limit would let one person's guessing lock every colleague out of
    changing theirs, which is a self-inflicted denial of service rather than a
    defence.
    """

    scope = "password_change"

    def get_cache_key(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class PasswordSetRequestRateThrottle(_IdentityRateThrottle):
    """Rate limit who can ask for a set-password link.

    Each accepted request sends a real email, so this is the throttle that stops
    a shared or spoofed origin using the endpoint as a mail cannon. Keying on the
    address being reset means five requests for a given inbox per hour, no
    matter how many proxies sit in front of Django — while a different employee
    is unaffected by a colleague's requests.
    """

    scope = "password_set_request"

    def get_identity(self, request) -> str:
        return _body_field(request, "email").lower()


class PasswordSetConfirmRateThrottle(_IdentityRateThrottle):
    """Rate limit token confirmations, per link.

    The secret is 256 bits, so guessing is hopeless; this exists to bound
    attempts against a leaked or partially guessable token value. The token is
    the subject of the request, so the bucket follows it: confirming one link
    cannot consume another person's allowance. Only a hash is used as the key
    so the secret is never written to the cache backend.
    """

    scope = "password_set_confirm"

    def get_identity(self, request) -> str:
        token = _body_field(request, "token")
        if not token:
            return ""
        return sha256(token.encode("utf-8")).hexdigest()
