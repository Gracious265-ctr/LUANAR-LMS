"""
Test settings for the LUANAR Leave Management System.

Fast, isolated test runs:

- MD5 password hasher (users are created in nearly every test)
- In-memory email backend
- Per-session disposable test database names so parallel ``manage.py test``
  runs (one per opencode session/branch) never collide on ``test_luanar_leave``
  and deadlock. See context/troubleshooting-notes.md (DeadlockDetected entry).

Usage::

    DJANGO_SETTINGS_MODULE=config.settings.test \\
        TEST_DB_NAME=test_luanar_leave_19 \\
        uv run manage.py test --keepdb --parallel auto

``TEST_DB_NAME`` defaults to ``test_luanar_leave`` so a plain
``--settings=config.settings.test`` run is indistinguishable from the old
behaviour.
"""

import os

from .base import *  # noqa: F401, F403

DEBUG = False

# Users are created constantly across the test suite; PBKDF2 is intentionally
# slow, so swap in the (test-only, insecure) MD5 hasher.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Distinct name per parallel session to avoid test-DB deadlocks.
DATABASES["default"]["TEST"] = {
    "NAME": os.environ.get("TEST_DB_NAME", "test_luanar_leave"),
}