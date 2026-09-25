"""
Fast Django test settings for LUANAR Leave Management System.

Test fixtures create users through PBKDF2 throughout the suite; swapping in a
fast hasher drops the run time dramatically without weakening the code under
test (password strength is a deployment setting, not a behavior tested here).
"""

from .base import *  # noqa: F401, F403
from .development import *  # noqa: F401, F403  (DEBUG / hosts / CORS)

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# The suite tests the *enqueue* contract, not the executed task: a render is
# dispatched with ``async_task`` and then run explicitly where the test is about
# the render. Development sets ``sync = True`` (see ``development.py``), and this
# module imports from it, so it is pinned back here — otherwise every approval in
# the suite would render inline and the "a fresh approval has a pending document"
# assertions could never hold.
Q_CLUSTER = {**Q_CLUSTER, "sync": False}  # noqa: F405

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