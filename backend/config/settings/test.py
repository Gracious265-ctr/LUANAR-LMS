"""
<<<<<<< HEAD
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
=======
Fast Django test settings for LUANAR Leave Management System.

Test fixtures create users through PBKDF2 throughout the suite; swapping in a
fast hasher drops the run time dramatically without weakening the code under
test (password strength is a deployment setting, not a behavior tested here).
"""

from .base import *  # noqa: F401, F403
from .development import *  # noqa: F401, F403  (DEBUG / hosts / CORS)

>>>>>>> feature/plans-teams
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

<<<<<<< HEAD
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Notifications (Unit 22): keep the whole existing suite free of Notification
# rows and email side effects. The notification tests enable dispatch
# explicitly via override_settings(NOTIFICATION_DISPATCHER="on").
NOTIFICATION_DISPATCHER = "off"

# Approval finalisation (Unit 23): keep the whole existing suite free of ledger
# deduction rows and generated documents. The Unit 23 tests enable finalisation
# explicitly via override_settings(APPROVAL_FINALISATION="on").
APPROVAL_FINALISATION = "off"

# Distinct name per parallel session to avoid test-DB deadlocks.
DATABASES["default"]["TEST"] = {
    "NAME": os.environ.get("TEST_DB_NAME", "test_luanar_leave"),
}
=======
# The suite tests the *enqueue* contract, not the executed task: a render is
# dispatched with ``async_task`` and then run explicitly where the test is about
# the render. Development sets ``sync = True`` (see ``development.py``), and this
# module imports from it, so it is pinned back here — otherwise every approval in
# the suite would render inline and the "a fresh approval has a pending document"
# assertions could never hold.
Q_CLUSTER = {**Q_CLUSTER, "sync": False}  # noqa: F405

# The suite must never reach a real mail relay.
#
# Django's test runner swaps in the locmem backend for the duration of the run,
# but that is an accident of the harness rather than a stated guarantee: once a
# developer configures real SMTP credentials in `.env`, a notification test that
# forgets to stub the send would quietly deliver mail to whatever address the
# seeded user happens to carry. Pinning the backend here makes the isolation
# explicit and independent of the local environment, the same argument as the
# Supabase clearing below.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
DEFAULT_FROM_EMAIL = "no-reply@test.luanar"

# Dispatch is asynchronous, so the suite asserts the *enqueue* contract and runs
# ``notifications.tasks.deliver_notification`` explicitly where the test is about
# delivery (see the documents suite for the same split).
NOTIFICATIONS_SYNC_SEND = False

# Never rewrite recipients in the suite: a test that wants the override turns it
# on deliberately.
EMAIL_DEV_RECIPIENT_OVERRIDE = []

# Pinned so a password-set link is deterministic and, more importantly, so a
# developer's local ``FRONTEND_URL`` can never leak into an assertion. ``DEBUG``
# is on under the test settings, which is what lets this stay plain HTTP.
FRONTEND_URL = "https://app.test.luanar"
PASSWORD_SET_TOKEN_LIFETIME_HOURS = 72

# The suite must never reach a real storage backend.
#
# `.env` is read at import time, so once a developer configures real Supabase
# credentials locally, any test that serializes a document without stubbing
# `get_supabase_client` starts making live HTTP calls and fails on whatever the
# project happens to contain. Those tests were previously green only because the
# developer's `.env` had no credentials at all, which made the pass accidental
# rather than hermetic. Clearing the values here makes the isolation explicit and
# independent of the local environment; the storage paths that assert real
# behavior stub the client themselves.
SUPABASE_URL = ""
SUPABASE_SERVICE_KEY = ""
>>>>>>> feature/plans-teams
