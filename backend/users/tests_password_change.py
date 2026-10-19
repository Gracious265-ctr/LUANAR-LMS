"""Changing a password from a live session.

This is the one password endpoint that is not token-based, and that difference
changes what has to be tested. A set-password link proves itself by being
unpredictable; a signed-in session proves nothing on its own, so this flow has
to earn the change instead — by re-checking the current password, by stamping a
watermark that kills the tokens it was meant to replace, and by telling the
account holder afterwards.

The tests below are grouped by that reasoning rather than by layer, because the
property that matters is a sequence: a token is minted, a password is changed,
and the token must stop working — through *both* the access path and the refresh
path, since the refresh endpoint never goes through DRF authentication and would
otherwise be the way around the whole thing.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditEntry
from notifications.models import NotificationOutbox
from notifications.tasks import deliver_notification
from users.models import PasswordSetToken
from users.services import WrongPasswordError, change_password, request_password_set

from .models import User

CHANGE_URL = "/api/v1/auth/password-change/"
REFRESH_URL = "/api/v1/auth/refresh/"

CURRENT_PASSWORD = "current pass phrase 7"
NEW_PASSWORD = "a whole new pass phrase 9"
WEAK_PASSWORD = "12345"


class ChangePasswordBase(TestCase):
    """A signed-in employee, and no broker in the way.

    ``enqueue_delivery`` dispatches on ``transaction.on_commit``, which a
    ``TestCase`` never reaches, so the queue is captured and a test that cares
    about the message calls ``deliver_notification`` itself.
    """

    def setUp(self):
        cache.clear()
        self.async_task = mock.patch("django_q.tasks.async_task").start()
        self.addCleanup(self.async_task.stop)

        self.user = User.objects.create_user(
            username="employee@luanar.ac.mw",
            email="employee@luanar.ac.mw",
            password=CURRENT_PASSWORD,
            first_name="Ester",
            last_name="Mwale",
            role=User.Role.EMPLOYEE,
        )
        self.client = APIClient()  # type: ignore[assignment]

    def tokens_for(self, user=None) -> tuple:
        """A fresh (access, refresh) pair, as the login endpoint issues them.

        Re-reads from the database first, because a token's fingerprint comes
        from the password hash held on the instance: a caller holding a
        ``self.user`` that a service has since changed would otherwise mint a
        token against the *old* hash and see it correctly rejected.
        """
        target = user or self.user
        target.refresh_from_db()
        refresh = RefreshToken.for_user(target)
        return str(refresh.access_token), str(refresh)

    def sign_in(self, user=None) -> str:
        self.client.force_authenticate(user=user or self.user)
        return (user or self.user).email

    def change(self, **overrides) -> None:
        payload = {
            "current_password": CURRENT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        }
        payload.update(overrides)
        with self.captureOnCommitCallbacks(execute=True):
            change_password(
                user=self.user,
                current_password=payload["current_password"],
                new_password=payload["new_password"],
            )

    def outbox_rows(self):
        return list(NotificationOutbox.objects.filter(user=self.user))


class CurrentPasswordTests(ChangePasswordBase):
    """Re-authentication is the whole point of this endpoint being different."""

    def test_the_new_password_works_and_the_old_one_does_not(self):
        self.change()

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(CURRENT_PASSWORD))

    def test_a_wrong_current_password_is_refused(self):
        with self.assertRaises(WrongPasswordError):
            self.change(current_password="not it at all 3")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_the_new_password_must_differ_from_the_current_one(self):
        # AUTH_PASSWORD_VALIDATORS does not cover this: Django's
        # UserAttributeSimilarityValidator compares username, name and email,
        # never the password being replaced.
        with self.assertRaises(DjangoValidationError):
            self.change(new_password=CURRENT_PASSWORD, confirm_password=CURRENT_PASSWORD)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_a_weak_new_password_is_refused_and_changes_nothing(self):
        with self.assertRaises(DjangoValidationError):
            self.change(new_password=WEAK_PASSWORD, confirm_password=WEAK_PASSWORD)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_a_wrong_current_password_writes_no_audit_entry(self):
        # The audit trail records what happened, not what was attempted. A
        # failed guess would otherwise sit in the permanent record looking like
        # a change.
        with self.assertRaises(WrongPasswordError):
            self.change(current_password="not it at all 3")

        self.assertFalse(
            AuditEntry.objects.filter(action=AuditEntry.Action.PASSWORD_CHANGED).exists()
        )


class SessionEvictionTests(ChangePasswordBase):
    """The tokens a password change is supposed to destroy.

    Both token types matter, and the refresh one is the interesting half: this
    app issues a 24-hour refresh token and never rotates or blacklists it, so a
    refresh path that skipped the watermark would let a captured token mint fresh
    access tokens for a full day after the owner changed their password.
    """

    def test_an_older_access_token_is_rejected_afterwards(self):
        access, _ = self.tokens_for()
        self.change()

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = fresh.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_an_older_refresh_token_cannot_mint_a_new_access_token(self):
        _, refresh = self.tokens_for()
        self.change()

        fresh = APIClient()  # type: ignore[assignment]
        response = fresh.post(REFRESH_URL, {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_token_issued_after_the_change_still_works(self):
        self.change()

        access, _ = self.tokens_for()
        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = fresh.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_changer_themselves_is_signed_out_too(self):
        # "Sign out everywhere" includes the device that did it, which is why
        # the frontend clears its cookies and returns to the sign-in page.
        access, _ = self.tokens_for()
        self.change()

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(
            fresh.get("/api/v1/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_the_rejection_explains_itself(self):
        # Somebody who changed a password to get rid of a stolen session should
        # be told the session is gone on purpose, not bounced to a bare form.
        # Both paths must say something: the access path's wording comes from
        # SimpleJWT itself, the refresh path's from users.authentication.
        access, refresh = self.tokens_for()
        self.change()

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        access_response = fresh.get("/api/v1/auth/me/")
        refresh_response = fresh.post(REFRESH_URL, {"refresh": refresh}, format="json")

        for response in (access_response, refresh_response):
            body = str(response.data).lower()
            self.assertIn("password", body)
            self.assertIn("chang", body)

    def test_an_untouched_account_keeps_its_sessions(self):
        # A token minted from the current hash is honoured, so no account is
        # signed out merely because this shipped.
        access, refresh = self.tokens_for()
        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        self.assertEqual(fresh.get("/api/v1/auth/me/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            fresh.post(REFRESH_URL, {"refresh": refresh}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_one_accounts_change_does_not_disturb_another(self):
        colleague = User.objects.create_user(
            username="colleague@luanar.ac.mw",
            email="colleague@luanar.ac.mw",
            password=CURRENT_PASSWORD,
        )
        theirs, their_refresh = self.tokens_for(colleague)

        self.change()

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {theirs}")
        self.assertEqual(fresh.get("/api/v1/auth/me/").status_code, status.HTTP_200_OK)
        self.assertEqual(
            fresh.post(REFRESH_URL, {"refresh": their_refresh}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_a_malformed_refresh_token_gets_the_ordinary_error(self):
        fresh = APIClient()  # type: ignore[assignment]
        response = fresh.post(REFRESH_URL, {"refresh": "nonsense"}, format="json")

        # The override must not invent a second error shape for a token it
        # cannot even parse; the base view's 401 is the canonical one.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_refresh_token_for_a_deleted_user_is_a_401_not_a_500(self):
        # A signed-in user whose account is deleted — routine when a database is
        # reset — holds a refresh token naming a user that no longer exists.
        # With ``CHECK_REVOKE_TOKEN`` on, SimpleJWT's refresh serializer would
        # raise ``User.DoesNotExist`` looking the user up, which is a 500 for
        # what is really just a stale session. The access path already answers
        # "User not found"; the refresh path must agree.
        _, refresh = self.tokens_for()
        self.user.delete()

        fresh = APIClient()  # type: ignore[assignment]
        response = fresh.post(REFRESH_URL, {"refresh": refresh}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MissingFingerprintTests(ChangePasswordBase):
    """A token with no fingerprint must not be a way around the watermark.

    SimpleJWT stamps ``CHECK_REVOKE_TOKEN``'s claim into every token it mints,
    so an absent claim means the token predates the setting. The access path has
    always treated that as stale — the built-in check compares the missing claim
    against the current hash and fails. Refresh once waved it through, and that
    was a hole rather than a courtesy: refresh would then mint a *new* access
    token stamped with the current fingerprint, which sails through the access
    check. A token captured before a password change would survive the change by
    exactly that route, which is the one thing this control exists to prevent.
    """

    def claimless_token(self) -> str:
        """A correctly signed, unexpired refresh token with the claim removed.

        Built the legitimate way and then stripped, so the only thing wrong with
        it is the thing under test: its signature and ``exp`` still verify, which
        is what makes the permissive branch look safe.
        """
        self.user.refresh_from_db()
        refresh = RefreshToken.for_user(self.user)
        del refresh[api_settings.REVOKE_TOKEN_CLAIM]
        return str(refresh)

    def test_refresh_rejects_a_token_with_no_fingerprint(self):
        response = APIClient().post(  # type: ignore[assignment]
            REFRESH_URL, {"refresh": self.claimless_token()}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("chang", str(response.data).lower())

    def test_the_access_path_agrees(self):
        # The two paths must reach the same verdict, or the permissive one is
        # reachable by simply choosing the other endpoint.
        token = RefreshToken.for_user(self.user)
        del token[api_settings.REVOKE_TOKEN_CLAIM]

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        self.assertEqual(
            fresh.get("/api/v1/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_a_claimless_token_cannot_outlive_a_password_change(self):
        # The end-to-end shape of the bypass: take a claim-less token, change the
        # password, then try to spend the token on the refresh endpoint.
        stolen = self.claimless_token()
        self.change()

        response = APIClient().post(  # type: ignore[assignment]
            REFRESH_URL, {"refresh": stolen}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)


class OutstandingLinkTests(ChangePasswordBase):
    """A set-password link must not outlive the password it would replace."""

    def test_a_live_set_password_link_is_invalidated(self):
        with self.captureOnCommitCallbacks(execute=True):
            token = request_password_set(self.user.email)

        # Live to begin with, so the assertion afterwards means something.
        token.refresh_from_db()
        self.assertIsNone(token.invalidated_at)

        self.change()

        token.refresh_from_db()
        self.assertIsNotNone(token.invalidated_at)

    def test_a_held_set_password_link_can_no_longer_set_anything(self):
        with self.captureOnCommitCallbacks(execute=True):
            request_password_set(self.user.email)
        secret = self.outbox_rows()[-1].body.partition("?token=")[2].split("\n", 1)[0].strip()

        self.change()

        confirm = APIClient()  # type: ignore[assignment]
        response = confirm.post(
            "/api/v1/auth/password-set/confirm/",
            {"token": secret, "password": NEW_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))


class NotificationTests(ChangePasswordBase):
    """A password change the owner never hears about helps nobody."""

    def test_a_notice_is_queued_to_the_address_on_file(self):
        self.change()

        rows = [r for r in self.outbox_rows() if r.kind == "password_changed"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].recipient_email, self.user.email)
        self.assertEqual(rows[0].role_label, "account")

    def test_the_notice_reaches_the_inbox(self):
        self.change()
        row = [r for r in self.outbox_rows() if r.kind == "password_changed"][0]

        deliver_notification(row.pk, recipients=[self.user.email])

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password", mail.outbox[0].subject.lower())

    def test_the_notice_never_carries_a_password(self):
        self.change()
        body = self.outbox_rows()[-1].body

        self.assertNotIn(CURRENT_PASSWORD, body)
        self.assertNotIn(NEW_PASSWORD, body)
        self.assertNotIn(self.user.password[:12], body)

    def test_the_queue_is_left_to_the_worker_not_the_request(self):
        self.sign_in()
        response = self.client.post(
            CHANGE_URL,
            {
                "current_password": CURRENT_PASSWORD,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Still queued, not sent inline: the request must not block on SMTP.
        row = [r for r in self.outbox_rows() if r.kind == "password_changed"][0]
        self.assertEqual(row.state, "pending")
        self.assertEqual(len(mail.outbox), 0)

    def test_an_account_with_no_address_is_skipped_rather_than_failing(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])

        self.change()

        self.assertEqual(
            [r for r in self.outbox_rows() if r.kind == "password_changed"], []
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))


class AuditTests(ChangePasswordBase):
    def test_a_change_is_recorded_against_the_account(self):
        self.change()

        entry = AuditEntry.objects.get(action=AuditEntry.Action.PASSWORD_CHANGED)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.USER_ACCOUNT)
        self.assertEqual(int(entry.target_id), self.user.pk)
        self.assertTrue(entry.detail["self_service"])

    def test_the_record_never_contains_a_password(self):
        self.change()

        entry = AuditEntry.objects.get(action=AuditEntry.Action.PASSWORD_CHANGED)
        self.assertNotIn(CURRENT_PASSWORD, str(entry.detail))
        self.assertNotIn(NEW_PASSWORD, str(entry.detail))


class EndpointTests(ChangePasswordBase):
    def setUp(self):
        super().setUp()
        self.payload = {
            "current_password": CURRENT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        }

    def test_an_authenticated_change_succeeds(self):
        self.sign_in()

        response = self.client.post(CHANGE_URL, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_the_response_tells_the_user_to_sign_in_again(self):
        self.sign_in()

        response = self.client.post(CHANGE_URL, self.payload, format="json")

        # Their own token is now invalid, so the UI has to clear its cookies and
        # say why rather than leaving them on a page that will 401.
        self.assertIn("sign in again", str(response.data).lower())

    def test_an_anonymous_caller_is_refused(self):
        response = self.client.post(CHANGE_URL, self.payload, format="json")

        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_a_wrong_current_password_is_a_400_naming_the_field(self):
        self.sign_in()
        payload = {**self.payload, "current_password": "not it at all 3"}

        response = self.client.post(CHANGE_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current password", str(response.data).lower())

    def test_a_mismatched_confirmation_is_a_400_before_any_lookup(self):
        self.sign_in()
        payload = {**self.payload, "confirm_password": "something else 4"}

        response = self.client.post(CHANGE_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("do not match", str(response.data).lower())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_a_weak_password_reports_the_validators_messages(self):
        self.sign_in()
        payload = {
            **self.payload,
            "new_password": WEAK_PASSWORD,
            "confirm_password": WEAK_PASSWORD,
        }

        response = self.client.post(CHANGE_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(str(response.data).strip())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CURRENT_PASSWORD))

    def test_reusing_the_current_password_is_refused(self):
        self.sign_in()
        payload = {
            **self.payload,
            "new_password": CURRENT_PASSWORD,
            "confirm_password": CURRENT_PASSWORD,
        }

        response = self.client.post(CHANGE_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_repeated_attempts_are_throttled(self):
        self.sign_in()
        payload = {**self.payload, "current_password": "guess 1"}

        for _ in range(10):
            self.client.post(CHANGE_URL, payload, format="json")

        response = self.client.post(CHANGE_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_the_throttle_is_per_user_not_per_address(self):
        # A shared office egress address must not let one person's attempts lock
        # a colleague out of changing their own password.
        colleague = User.objects.create_user(
            username="colleague@luanar.ac.mw",
            email="colleague@luanar.ac.mw",
            password=CURRENT_PASSWORD,
        )
        self.sign_in()
        payload = {**self.payload, "current_password": "guess 1"}
        for _ in range(10):
            self.client.post(CHANGE_URL, payload, format="json")

        other = APIClient()  # type: ignore[assignment]
        other.force_authenticate(user=colleague)
        response = other.post(CHANGE_URL, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FirstPasswordEvictionTests(ChangePasswordBase):
    """Setting a password for the first time revokes, too.

    Nobody is signed out by this one — the account was unusable a moment ago, so
    there was no working session to end. What matters is the other direction: a
    token minted while the password was still the unusable placeholder must not
    become a way in once a real password exists.
    """

    def set_first_password(self) -> None:
        """Run the real set-password flow against an account with no password."""
        from users.services import confirm_password_set

        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])

        with self.captureOnCommitCallbacks(execute=True):
            request_password_set(self.user.email)
            row = NotificationOutbox.objects.filter(user=self.user).order_by(
                "created_at"
            )[0]
            _, _, query = row.body.partition("?token=")
            secret = query.split("\n", 1)[0].strip()
            confirm_password_set(secret, NEW_PASSWORD)

    def test_a_first_password_is_actually_set(self):
        self.set_first_password()

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_a_token_from_before_the_first_password_is_rejected(self):
        # Minted while the stored password was the unusable placeholder, whose
        # fingerprint is not the one the account carries afterwards.
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        access, _ = self.tokens_for()

        self.set_first_password()

        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(
            fresh.get("/api/v1/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_a_token_from_before_the_first_password_cannot_be_refreshed(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        _, refresh = self.tokens_for()

        self.set_first_password()

        fresh = APIClient()  # type: ignore[assignment]
        response = fresh.post(REFRESH_URL, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_token_minted_after_the_first_password_works(self):
        self.set_first_password()

        access, _ = self.tokens_for()
        fresh = APIClient()  # type: ignore[assignment]
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(
            fresh.get("/api/v1/auth/me/").status_code, status.HTTP_200_OK
        )
