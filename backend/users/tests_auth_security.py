"""Authentication and session-security behaviour, one property per test.

These are the rules that decide whether a request is who it claims to be: the
credential endpoints must be rate limited per subject rather than per proxy
address, sign-out must revoke the refresh token server-side, and a deactivated
account must not be able to sign in.
"""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from .models import User

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
PASSWORD_SET_REQUEST_URL = "/api/v1/auth/password-set/request/"
PASSWORD_SET_CONFIRM_URL = "/api/v1/auth/password-set/confirm/"

PASSWORD = "a-long-enough-password"
WRONG_PASSWORD = "not-the-password"


class ThrottleTestCase(TestCase):
    """Every test starts with empty throttle counters."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()  # type: ignore[assignment]


class LoginThrottleTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.alice = User.objects.create_user(
            username="alice@throttle.test",
            email="alice@throttle.test",
            password=PASSWORD,
        )
        self.bob = User.objects.create_user(
            username="bob@throttle.test",
            email="bob@throttle.test",
            password=PASSWORD,
        )

    def _attempt(self, email, password=WRONG_PASSWORD):
        return self.client.post(LOGIN_URL, {"email": email, "password": password})

    def test_guesses_against_one_account_are_limited(self):
        for _ in range(10):
            self.assertEqual(self._attempt(self.alice.email).status_code, 401)

        response = self._attempt(self.alice.email)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_one_account_being_guessed_does_not_lock_out_a_colleague(self):
        # Django only ever sees the Next.js proxy's address, so an IP-keyed
        # throttle would make the ten attempts above lock out the whole
        # institution. Keying on the submitted account is what keeps Bob out of
        # Alice's bucket.
        for _ in range(10):
            self._attempt(self.alice.email)

        response = self._attempt(self.bob.email, PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)  # type: ignore[union-attr]

    def test_an_authenticated_caller_cannot_opt_out_of_the_limit(self):
        # ``AnonRateThrottle`` returns no key for an authenticated request,
        # which would let anybody holding any valid token brute-force a login
        # without ever being counted. The login throttle must bind on the
        # endpoint's own subject even when the request carries a token.
        self.client.force_authenticate(user=self.bob)
        for _ in range(10):
            self._attempt(self.alice.email)

        response = self._attempt(self.alice.email)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class PasswordSetRequestThrottleTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="reset@throttle.test",
            email="reset@throttle.test",
            password=None,
        )
        self.user.set_unusable_password()
        self.user.save()
        self.other = User.objects.create_user(
            username="other@throttle.test",
            email="other@throttle.test",
            password=None,
        )
        self.other.set_unusable_password()
        self.other.save()
        self.issue_patcher = mock.patch("users.views.request_password_set")
        self.issue = self.issue_patcher.start()
        self.addCleanup(self.issue_patcher.stop)

    def test_requests_for_one_inbox_are_limited(self):
        for _ in range(5):
            response = self.client.post(
                PASSWORD_SET_REQUEST_URL, {"email": self.user.email}
            )
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        response = self.client.post(
            PASSWORD_SET_REQUEST_URL, {"email": self.user.email}
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(self.issue.call_count, 5)

    def test_a_colleagues_requests_do_not_consume_another_inbox(self):
        for _ in range(5):
            self.client.post(PASSWORD_SET_REQUEST_URL, {"email": self.user.email})

        response = self.client.post(
            PASSWORD_SET_REQUEST_URL, {"email": self.other.email}
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)


class PasswordSetConfirmThrottleTests(ThrottleTestCase):
    def test_attempts_are_limited_per_link_not_across_the_institution(self):
        token = "a" * 43

        for _ in range(20):
            response = self.client.post(
                PASSWORD_SET_CONFIRM_URL, {"token": token, "password": "whatever"}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            PASSWORD_SET_CONFIRM_URL, {"token": token, "password": "whatever"}
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # A different link has its own bucket, so one person exhausting theirs
        # cannot stop everybody else from setting a password.
        other = self.client.post(
            PASSWORD_SET_CONFIRM_URL,
            {"token": "b" * 43, "password": "whatever"},
        )
        self.assertEqual(other.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutRevocationTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="logout@throttle.test",
            email="logout@throttle.test",
            password=PASSWORD,
        )
        login = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": PASSWORD},
        )
        self.refresh = login.data["refresh"]  # type: ignore[index]

    def test_sign_out_blacklists_the_refresh_token(self):
        self.assertEqual(BlacklistedToken.objects.count(), 0)

        response = self.client.post(LOGOUT_URL, {"refresh": self.refresh})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(BlacklistedToken.objects.count(), 1)

        # A copied token is now useless: the refresh path refuses it.
        retry = self.client.post(REFRESH_URL, {"refresh": self.refresh})
        self.assertEqual(retry.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_expired_or_malformed_token_still_answers_204(self):
        for raw in ("not-a-token", ""):
            response = self.client.post(LOGOUT_URL, {"refresh": raw})
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_a_body_less_sign_out_answers_204(self):
        # Nothing to revoke, but the caller still expects to be signed out, and
        # a parser error must not turn that into a 400.
        response = self.client.post(LOGOUT_URL)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_logging_out_twice_is_not_an_error(self):
        self.client.post(LOGOUT_URL, {"refresh": self.refresh})
        response = self.client.post(LOGOUT_URL, {"refresh": self.refresh})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class InactiveAccountTests(ThrottleTestCase):
    def test_a_deactivated_account_cannot_sign_in(self):
        user = User.objects.create_user(
            username="inactive@throttle.test",
            email="inactive@throttle.test",
            password=PASSWORD,
            is_active=False,
        )

        response = self.client.post(
            LOGIN_URL, {"email": user.email, "password": PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)  # type: ignore[operator]

    def test_deactivating_an_account_ends_an_existing_refresh_token(self):
        user = User.objects.create_user(
            username="ended@throttle.test",
            email="ended@throttle.test",
            password=PASSWORD,
        )
        login = self.client.post(
            LOGIN_URL, {"email": user.email, "password": PASSWORD}
        )
        refresh = login.data["refresh"]  # type: ignore[index]

        user.is_active = False
        user.save(update_fields=["is_active"])

        response = self.client.post(REFRESH_URL, {"refresh": refresh})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
