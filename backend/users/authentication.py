"""Session revocation on a password change.

Changing a password is supposed to mean "everywhere else is signed out". Without
this, it would not: the app issues a 24-hour ``refresh`` token and never rotates
or blacklists it, and signing out only clears cookies without revoking anything
server-side. A token captured before the change would keep minting fresh access
tokens for a full day afterwards — which is precisely the situation a person is
trying to escape when they change a password they think is stolen.

SimpleJWT has this mechanism already, as ``CHECK_REVOKE_TOKEN``: a fingerprint of
the password hash is written into every token, and a token whose fingerprint no
longer matches the account is rejected. Turning that on is the whole fix for the
*access* path, and it is exact — a token is stale because the hash it names is
not the hash the account has, which avoids the second-granularity guessing an
``iat`` comparison would need.

The *refresh* path is not covered by it. ``TokenRefreshView`` hands the raw token
straight to ``TokenRefreshSerializer``, which mints a new access token without
consulting the user record at all, so a pre-change refresh token would keep
working and minting access tokens that pass the check above. That is why this
module exists, and why the check is written once here and used from both places.

Both call sites must reach the same verdict, including for a token that carries no
fingerprint at all. SimpleJWT's access path treats an absent claim as a mismatch,
so this module does too; were it to wave one through, refresh would hand it a
newly stamped access token and the revocation would be trivially bypassed. One
shared function, one policy, no room for the two paths to drift.
"""

from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password


# Reused verbatim by both call sites, so somebody signed out mid-session is told
# why rather than being bounced to a bare login form. It is a login problem with
# a known cause, and a known cause is worth saying: someone who changed their
# password to get rid of a stolen session should know the session is gone on
# purpose.
PASSWORD_CHANGED_DETAIL = (
    "Your password was changed, so other sessions were signed out. "
    "Please sign in again."
)


def assert_token_matches_password(user, token) -> None:
    """Raise ``AuthenticationFailed`` if ``token`` predates the current password.

    A token minted before a password change carries the old password's
    fingerprint. Comparing it against the account's current hash needs no extra
    column, no clock comparison, and no tolerance for token timestamp precision:
    either the hash matches or the token is from before the change.
    """
    if not api_settings.CHECK_REVOKE_TOKEN:
        # The setting governs the access path. Honouring it here too means the
        # two cannot disagree: if the check is off, nothing is rejected, rather
        # than the refresh endpoint quietly enforcing a policy the rest of the
        # app has turned off.
        return

    # A token carrying no fingerprint is treated as stale, not waved through. A
    # missing claim can only come from a token minted before this setting was on,
    # and the access path already rejects exactly that token — SimpleJWT compares
    # the absent claim against the current hash and fails. Allowing it here would
    # leave the two paths disagreeing in the one direction that matters: refresh
    # would accept a claim-less token and mint a *fresh* access token stamped
    # with the current fingerprint, which then passes the access check. A token
    # captured before a password change would survive the change by that route.
    # Failing closed costs one re-login for anyone holding a pre-setting token,
    # which is the correct price for a control whose whole purpose is to end
    # sessions. There are no server-side sessions to migrate: the app is
    # stateless JWT, so "every session in the database" does not exist.
    fingerprint = (token or {}).get(api_settings.REVOKE_TOKEN_CLAIM)
    if fingerprint != get_md5_hash_password(user.password):
        raise AuthenticationFailed(PASSWORD_CHANGED_DETAIL, code="password_changed")
