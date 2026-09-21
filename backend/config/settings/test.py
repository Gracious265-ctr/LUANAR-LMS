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