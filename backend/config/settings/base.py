"""
Django base settings for LUANAR Leave Management System.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")

DEBUG = env("DEBUG", default=False)

ALLOWED_HOSTS = env("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "django_q",
    # Local apps
    "users",
    "leave",
    "organisation",
    "teams",
    "approvals",
    "workflows",
    "notifications",
    "plans",
    "documents",
    "audit",
    "launcher",
    "directory",
    "org",
    "leave_config",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://luanar:luanar@localhost:5432/luanar_leave",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Blantyre"
USE_I18N = True
USE_TZ = True

# Leave validation (Unit 14). The rules provider is the single source of
# leave-type rules, employees, financial years, public holidays and balances.
# Since Unit 20 it is backed by the real HR-track tables
# (DatabaseRulesProvider); see docs/leave-rules-provider-contract.md.
LEAVE_RULES_PROVIDER = "leave.providers.database.DatabaseRulesProvider"
LEAVE_BLOCKING_STATUSES = ["submitted", "pending", "approved"]

# Leave application tracking (Unit 15). The tracking provider supplies the
# read-only workflow payload from the real workflow tables since Unit 21
# (see docs/leave-rules-provider-contract.md).
LEAVE_TRACKING_PROVIDER = "leave.tracking.database_provider.DatabaseTrackingProvider"

# Approver workflow (Unit 16). The workflow provider resolves the stage chain
# for an application from the real HR-track Workflow/WorkflowStage configuration
# (Unit 21); see docs/workflow-to-approver-routing.md.
WORKFLOW_PROVIDER = "workflows.providers.DatabaseWorkflowProvider"

# Leave cancellation balance (Unit 18). The balance provider answers how many
# annual days an approved application deducted and records the restoration when
# a cancellation is finally approved.
LEAVE_BALANCE_PROVIDER = (
    "leave.cancellations.providers.LedgerBalanceProvider"
)

# Organisation data provider (Unit: External Organization Data Provider).
# The provider supplies employees, grades, org units and role holders; only
# "fixture" ships for now, "api" is reserved for the real directory and
# raises until it exists (see directory/factory.py).
ORG_DATA_BACKEND = env("ORG_DATA_BACKEND", default="fixture")

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        # Asking for a set-password link is throttled harder than confirming one:
        # a request emails a real person, so a shared office IP must not be able
        # to mail the same person all afternoon. Confirming a 32-byte secret is
        # not guessable, so it only needs the same rough ceiling as login.
        "password_set_request": "5/hour",
        "password_set_confirm": "20/hour",
        # Per user, not per IP: a shared office address must not let one person's
        # attempts lock a colleague out of changing their own password.
        "password_change": "10/hour",
    },
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    # A fingerprint of the password is written into every token, and tokens that
    # no longer match the account's current hash are rejected. Since this app
    # neither rotates nor blacklists refresh tokens, this is the entire of
    # session revocation — without it, changing a password would leave every
    # other device signed in for the rest of the refresh token's 24 hours.
    "CHECK_REVOKE_TOKEN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS
CORS_ALLOWED_ORIGINS = env(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000"],
)
CORS_ALLOW_CREDENTIALS = True

# Django-Q2 (ORM broker using the default database)
Q_CLUSTER = {
    "name": "luanar_leave",
    "workers": 4,
    "recycle": 500,
    "timeout": 60,
    "compress": True,
    "save_limit": 250,
    "queue_limit": 500,
    "cpu_affinity": 1,
    "orm": "default",
}

# Email. Google SMTP during development and testing, replaceable with the
# LUANAR institutional relay through ``.env`` alone: the transport is selected
# here rather than hard-coded, so a tree with no credentials still prints to the
# console instead of failing a login against smtp.gmail.com.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
# A relay that has stopped answering must not hold a request open indefinitely:
# the delivery runs on a worker, but a wedged socket still costs that worker.
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
# Gmail refuses a ``From:`` address it is not authorised to send as, so the
# composers' ``no-reply@luanar.ac.mw`` fallback only survives on the console
# backend. ``notifications.tasks`` turns a real SMTP backend with this unset into
# a recorded failure with an explanation instead of a silent 550.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="")

# Notification dispatch. ``False`` hands delivery to a django-q2 worker;
# ``True`` runs it inline at the enqueue point, which is what a single-process
# development server needs so a submitted application still sends its mail.
NOTIFICATIONS_SYNC_SEND = env.bool("NOTIFICATIONS_SYNC_SEND", default=False)

# Development-only recipient override. The seeded users carry undeliverable
# addresses (``@test.luanar``), so a live SMTP smoke test would otherwise 550 on
# every recipient. This routes the messages into one real inbox instead, and is
# honoured *only* under ``DEBUG`` — outside it, the override is refused and the
# real recipients are used, so it can never mask a wrong recipient in
# production.
EMAIL_DEV_RECIPIENT_OVERRIDE = env.list("EMAIL_DEV_RECIPIENT_OVERRIDE", default=[])

# The absolute base URL of the Next.js app. Password-set links are only usable
# outside the backend, so this is what turns a token into something a person can
# click; ``notifications.accounts`` refuses to put a live secret on a plain-HTTP
# link when DEBUG is off.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# How long a set-password link stays usable. Deliberately generous: the mail
# reaches an inbox that is read at a human pace, and a 72h window still bounds a
# leaked inbox search result. Issuing a new link invalidates the previous one.
PASSWORD_SET_TOKEN_LIFETIME_HOURS = env.int(
    "PASSWORD_SET_TOKEN_LIFETIME_HOURS", default=72
)

# Supabase Storage
SUPABASE_URL = env("SUPABASE_URL", default="")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", default="")
SUPABASE_BUCKET = env("SUPABASE_BUCKET", default="leave-documents")
SUPABASE_SIGNED_URL_EXPIRY = env.int("SUPABASE_SIGNED_URL_EXPIRY", default=3600)
