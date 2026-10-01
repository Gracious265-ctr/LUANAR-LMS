from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Rate limit anonymous login attempts to slow credential brute-forcing."""

    scope = "login"


class PasswordChangeRateThrottle(UserRateThrottle):
    """Rate limit password changes so the current password cannot be guessed.

    Per *user*, not per IP. The thing being guessed is one person's current
    password, and the office this is built for shares an egress address: a
    per-IP limit would let one person's guessing lock every colleague out of
    changing theirs, which is a self-inflicted denial of service rather than a
    defence.
    """

    scope = "password_change"


class PasswordSetRequestRateThrottle(AnonRateThrottle):
    """Rate limit who can ask for a set-password link.

    Each accepted request sends a real email, so this is the throttle that stops
    a shared or spoofed origin using the endpoint as a mail cannon.
    """

    scope = "password_set_request"


class PasswordSetConfirmRateThrottle(AnonRateThrottle):
    """Rate limit token confirmations.

    The secret is 256 bits, so guessing is hopeless; this exists to bound
    attempts against a leaked or partially guessable token value.
    """

    scope = "password_set_confirm"
