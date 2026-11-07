"""Production settings for the LUANAR Leave Management System.

This is the module :mod:`config.wsgi` and :mod:`config.asgi` load by default, so
a deployment that does not set ``DJANGO_SETTINGS_MODULE`` gets these rules
rather than the development module's ``DEBUG = True``, wildcard hosts, and
allow-all CORS. ``manage.py`` keeps development as its default so ``runserver``
stays convenient.

Everything here is either a fail-closed default or an env override. The two
required values — ``SECRET_KEY`` and ``ALLOWED_HOSTS`` — stop the process at
import time rather than letting a misconfigured deployment run with a known
signing key or answer every request with a confusing 400.

A shared cache is optional but strongly recommended: DRF's throttles keep their
counters in Django's cache, and the default per-process cache means a
multi-worker deployment multiplies every rate limit by the number of workers.
Set ``CACHE_URL`` (for example ``redis://127.0.0.1:6379/1``) to share them.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = False

# ---------------------------------------------------------------------------
# Required deployment values
# ---------------------------------------------------------------------------

# The placeholder key is public. With it, anyone who can read this repository
# can mint a valid JWT for any account, including the bootstrap superuser —
# signing-key secrecy *is* the authentication boundary for a stateless JWT app.
INSECURE_SECRET_KEY = "django-insecure-change-me-in-production"
if SECRET_KEY == INSECURE_SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY is still the insecure development default. Set SECRET_KEY "
        "to a unique random value before running in production. Generate one "
        'with: python -c "from django.core.management.utils import '
        'get_random_secret_key; print(get_random_secret_key())"'
    )

# A short or low-entropy key is nearly as bad: it is guessable offline from one
# captured token, which is the same total bypass as the placeholder. These are
# the thresholds Django's own ``security.W009`` uses.
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY is too weak for production: it must be at least 50 "
        "characters with a reasonable spread of distinct characters. Generate "
        'one with: python -c "from django.core.management.utils import '
        'get_random_secret_key; print(get_random_secret_key())"'
    )

# An empty host list makes Django reject every request with a 400. That is
# fail-closed, but it looks like an outage; say what is wrong at boot instead.
if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS is empty. Set it to the hostnames this deployment "
        "serves, for example ALLOWED_HOSTS=leave.example.edu."
    )

# A password-set link is a live secret. The notification layer refuses to build
# one over plain HTTP when DEBUG is off; refusing to start makes that failure
# visible to the operator rather than to the employee who never receives mail.
if not str(FRONTEND_URL).startswith("https://"):  # noqa: F405
    raise ImproperlyConfigured(
        "FRONTEND_URL must be an https:// address in production. A "
        "set-password link is a bearer secret and must not travel over plain "
        "HTTP."
    )

# ---------------------------------------------------------------------------
# HTTPS and browser-facing hardening
# ---------------------------------------------------------------------------

# TLS terminates at the reverse proxy in front of this process. Trusting the
# proxy's forwarded scheme is what lets Django know the original request was
# HTTPS when it decides whether to redirect and whether to set secure cookies.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env.bool("USE_X_FORWARDED_HOST", default=True)

# Redirect plain HTTP to HTTPS. Disable only for a deployment that terminates
# TLS in a way that cannot forward the original scheme.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

# The Django admin and any session-backed surface use cookies. These keep them
# off plain HTTP and out of JavaScript, and stop another site from riding an
# admin session (``SameSite`` is defence in depth alongside CSRF tokens).
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS. The defaults are conservative enough for a university deployment that
# may still have a plain-HTTP service on another subdomain; opt in to
# subdomains/preload only once every one of them is HTTPS.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# The admin is served from this host over HTTPS; Django needs to be told that
# origin or its CSRF check refuses the login form.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
#
# Browsers never call Django directly: the Next.js server holds the JWTs in
# httpOnly cookies and proxies every API request itself. So production needs no
# CORS at all, and certainly not credentialed CORS. A deployment that does put a
# browser in front of Django can name its origins explicitly.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405

# Behind one reverse proxy, DRF should read the client address from the last
# entry the proxy appended rather than the whole forwarded chain. A deployment
# with a different topology can override this.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "NUM_PROXIES": env.int("NUM_PROXIES", default=1),
}

# ---------------------------------------------------------------------------
# Shared cache (throttle counters)
# ---------------------------------------------------------------------------
#
# Without this, each worker keeps its own counters, so four workers turn
# ``10/min`` into roughly ``40/min`` and the limits stop meaning what the
# settings say. ``locmem://`` is the fallback for a single-process deployment;
# set ``CACHE_URL`` to Redis or Memcached when running several workers.
CACHE_URL = env("CACHE_URL", default="")
if CACHE_URL:
    CACHES = {"default": env.cache_url("CACHE_URL")}
