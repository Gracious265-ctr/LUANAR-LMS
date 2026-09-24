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
    "workflows",
    "notifications",
    "documents",
    "audit",
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
# leave-type rules, employees, financial years, public holidays and balances;
# the database provider backs it with the real HR-track models (Unit 20, see
# docs/leave-rules-provider-contract.md).
LEAVE_RULES_PROVIDER = "leave.providers.database.DatabaseRulesProvider"
LEAVE_BLOCKING_STATUSES = ["submitted", "pending", "correction_required", "approved"]

# Leave application tracking (Unit 15). The tracking provider supplies the
# read-only workflow payload; the fixture provider is replaced by the real
# workflow-backed provider in Unit 20 (see docs/leave-rules-provider-contract.md).
LEAVE_TRACKING_PROVIDER = "leave.tracking.fixture_provider.FixtureTrackingProvider"

# Approval workflow provider (Unit 16). Swappable so the real Unit 6 workflow
# backend can drop in at Unit 20 without touching the decision service (see
# docs/leave-rules-provider-contract.md for the handoff pattern).
WORKFLOW_PROVIDER = "workflows.fixture_provider.FixtureWorkflowProvider"

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
    },
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
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

# Email (console backend for development)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Supabase Storage
SUPABASE_URL = env("SUPABASE_URL", default="")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", default="")
SUPABASE_BUCKET = env("SUPABASE_BUCKET", default="leave-documents")
SUPABASE_SIGNED_URL_EXPIRY = env.int("SUPABASE_SIGNED_URL_EXPIRY", default=3600)

# Leave document storage (Unit 19). Storage is abstracted; the dev backend
# writes to local disk so uploads/downloads work without Supabase credentials,
# and the production storage technology stays replaceable per architecture.md.
LEAVE_STORAGE_BACKEND = "leave.storage.development.DevelopmentStorageBackend"
LEAVE_STORAGE_ROOT = Path(BASE_DIR.parent, "storage")
LEAVE_DOCUMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
LEAVE_DOCUMENT_ALLOWED_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
)
