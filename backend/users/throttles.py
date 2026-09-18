from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Rate limit anonymous login attempts to slow credential brute-forcing."""

    scope = "login"
