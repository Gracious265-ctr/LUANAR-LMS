"""The set-password flow, end to end.

An HR-created account has no password, so this is the only thing that lets a new
employee sign in — and therefore the only way any notification they are ever
sent can actually arrive. These tests cover the three properties the flow has to
hold regardless of how it is exercised: the secret is never stored in the clear,
only one link per account is ever live, and the request endpoint cannot be used
to discover who has an account.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import authenticate
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from notifications.models import NotificationOutbox
from notifications.tasks import deliver_notification
from users.models import EmployeeProfile, PasswordSetToken
from users.services import (
    InvalidPasswordSetToken,
    confirm_password_set,
    hash_token,
    request_password_set,
    token_is_usable,
)

from .models import User

REQUEST_URL = "/api/v1/auth/password-set/request/"
VALIDATE_URL = "/api/v1/auth/password-set/validate/"
CONFIRM_URL = "/api/v1/auth/password-set/confirm/"

NEW_PASSWORD = "correct horse battery staple"
WEAK_PASSWORD = "12345"


class PasswordSetBase(TestCase):
    """An account with no password, and no broker in the way.

    The queue step is stubbed so a test asserts the *enqueue* contract and runs
    ``deliver_notification`` itself where the point is the message itself; the
    throttle cache is cleared because DRF keys its counters per IP, and the
    suite shares one.
    """

    def setUp(self):
        cache.clear()
        self.async_task = mock.patch("django_q.tasks.async_task").start()
        self.addCleanup(self.async_task.stop)

        self.user = User.objects.create_user(
            username="new.employee@luanar.ac.mw",
            email="new.employee@luanar.ac.mw",
            password=None,
            first_name="New",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )
        self.user.set_unusable_password()
        self.user.save()

        self.hr_user = User.objects.create_user(
            username="hr@luanar.ac.mw",
            email="hr@luanar.ac.mw",
            password=NEW_PASSWORD,
            first_name="Hannah",
            last_name="Rhodes",
            role=User.Role.HR,
        )

    def issue(self, email=None, *, actor=None):
        """Issue a link the way production does, dispatch included.

        ``enqueue_delivery`` defers to ``transaction.on_commit``, which a
        ``TestCase`` never reaches — hence the capture, so a test that asserts
        the enqueue contract sees the same call the broker would.
        """
        with self.captureOnCommitCallbacks(execute=True):
            return request_password_set(email or self.user.email, actor=actor)

    def token_rows(self, user=None) -> list[PasswordSetToken]:
        return list(
            PasswordSetToken.objects.select_related("user").filter(
                user=user or self.user
            )
        )

    def outbox_rows(self, user=None):
        return list(
            NotificationOutbox.objects.filter(user=user or self.user).order_by(
                "created_at"
            )
        )

    def secret_from_mail(self, index: int = 0) -> str:
        """The token in the link the person was actually emailed."""
        row = self.outbox_rows()[index]
        _, _, query = row.body.partition("?token=")
        return query.split("\n", 1)[0].strip()


class TokenIssuanceTests(PasswordSetBase):
    """Issuing a link: what is stored, what is sent, what is audited."""

    def test_request_creates_one_live_token_and_queues_the_email(self):
        token = self.issue()

        self.assertIsNotNone(token)
        self.assertEqual(self.token_rows(), [token])

        rows = self.outbox_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].kind, "password_set")
        self.assertEqual(rows[0].role_label, "account")
        self.assertEqual(rows[0].recipient_email, self.user.email)
        self.assertEqual(rows[0].state, "pending")
        # Exactly one subject: the account, and nothing else.
        self.assertEqual(rows[0].user_id, self.user.pk)
        self.assertIsNone(rows[0].application_id)
        self.assertIsNone(rows[0].cancellation_id)
        self.assertIsNone(rows[0].plan_id)

        self.async_task.assert_called_once()
        self.assertEqual(
            self.async_task.call_args.args[0],
            "notifications.tasks.deliver_notification",
        )

    def test_delivered_link_carries_the_secret_and_lives_72_hours(self):
        token = self.issue()
        deliver_notification(self.outbox_rows()[0].pk)

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("https://app.test.luanar/set-password?token=", body)
        self.assertTrue(token_is_usable(self.secret_from_mail()))

        lifetime = token.expires_at - timezone.now()
        self.assertGreater(lifetime, timedelta(hours=71))
        self.assertLess(lifetime, timedelta(hours=73))

        self.outbox_rows()[0].refresh_from_db()
        self.assertEqual(self.outbox_rows()[0].state, "sent")

    def test_only_the_hash_is_persisted(self):
        self.issue()
        secret = self.secret_from_mail()
        token = self.token_rows()[0]

        self.assertNotEqual(token.token_hash, secret)
        self.assertEqual(token.token_hash, hashlib.sha256(secret.encode()).hexdigest())
        self.assertEqual(len(token.token_hash), 64)

    def test_request_is_audited(self):
        self.issue()

        entry = AuditEntry.objects.filter(
            action=AuditEntry.Action.PASSWORD_SET_REQUESTED
        ).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.USER_ACCOUNT)
        self.assertEqual(entry.target_id, str(self.user.pk))
        self.assertTrue(entry.detail["issued_by_hr"] is False)

    def test_hr_actor_is_recorded_on_the_token_and_the_audit(self):
        self.issue(actor=self.hr_user)

        self.assertEqual(self.token_rows()[0].issued_by, self.hr_user)
        entry = AuditEntry.objects.filter(
            action=AuditEntry.Action.PASSWORD_SET_REQUESTED
        ).get()
        self.assertEqual(entry.actor, self.hr_user)
        self.assertTrue(entry.detail["issued_by_hr"])

    def test_resend_invalidates_the_previous_link(self):
        self.issue()
        first_secret = self.secret_from_mail()
        first = self.token_rows()[0]

        self.issue(actor=self.hr_user)

        first.refresh_from_db()
        self.assertIsNotNone(first.invalidated_at)
        self.assertIsNone(first.used_at)
        self.assertFalse(token_is_usable(first_secret))
        self.assertTrue(token_is_usable(self.secret_from_mail(index=1)))
        # One live link, and both issuances recorded.
        self.assertEqual(len(self.outbox_rows()), 2)
        self.assertEqual(
            PasswordSetToken.objects.filter(
                user=self.user, invalidated_at__isnull=True, used_at__isnull=True
            ).count(),
            1,
        )

    def test_unknown_address_sends_nothing(self):
        self.assertIsNone(request_password_set("nobody@luanar.ac.mw"))

        self.assertEqual(self.token_rows(user=self.user), [])
        self.assertEqual(NotificationOutbox.objects.count(), 0)
        self.assertEqual(mail.outbox, [])

    def test_deactivated_account_is_refused(self):
        self.user.is_active = False
        self.user.save()

        self.assertIsNone(request_password_set(self.user.email))
        self.assertEqual(NotificationOutbox.objects.count(), 0)

    def test_account_without_an_email_is_refused(self):
        self.user.email = ""
        self.user.username = "no-address"
        self.user.save()

        self.assertIsNone(request_password_set(""))
        self.assertEqual(NotificationOutbox.objects.count(), 0)

    @override_settings(DEBUG=False, FRONTEND_URL="http://app.luanar.ac.mw")
    def test_a_plain_http_link_is_refused_outside_debug(self):
        with self.assertRaises(Exception) as caught:
            request_password_set(self.user.email)
        self.assertIn("HTTPS", str(caught.exception))

        # Nothing durable either: the whole issuance rolled back.
        self.assertEqual(PasswordSetToken.objects.count(), 0)
        self.assertEqual(NotificationOutbox.objects.count(), 0)


class ConfirmPasswordTests(PasswordSetBase):
    """Consuming a link: it must work once, and only once."""

    def live_secret(self) -> str:
        """A token that was just issued, read back out of the email body."""
        self.issue()
        return self.secret_from_mail()

    def test_confirm_sets_the_password_and_lets_them_sign_in(self):
        secret = self.live_secret()

        user = confirm_password_set(secret, NEW_PASSWORD)

        self.user.refresh_from_db()
        self.assertEqual(user.pk, self.user.pk)
        self.assertTrue(self.user.has_usable_password())
        self.assertIsNotNone(
            authenticate(username=self.user.email, password=NEW_PASSWORD)
        )

    def test_token_is_consumed_and_no_other_link_survives(self):
        self.issue()
        superseded = self.secret_from_mail()
        self.issue()
        live = self.secret_from_mail(index=1)

        confirm_password_set(live, NEW_PASSWORD)

        self.assertEqual(
            PasswordSetToken.objects.filter(
                user=self.user, used_at__isnull=True, invalidated_at__isnull=True
            ).count(),
            0,
        )
        self.assertFalse(token_is_usable(live))
        self.assertFalse(token_is_usable(superseded))

    def test_a_token_cannot_be_used_twice(self):
        secret = self.live_secret()
        confirm_password_set(secret, NEW_PASSWORD)

        with self.assertRaises(InvalidPasswordSetToken):
            confirm_password_set(secret, "a whole different password 123")

    def test_expired_token_is_refused(self):
        secret = self.live_secret()
        PasswordSetToken.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

        self.assertFalse(token_is_usable(secret))
        with self.assertRaises(InvalidPasswordSetToken):
            confirm_password_set(secret, NEW_PASSWORD)

    def test_deactivated_account_cannot_use_a_live_link(self):
        secret = self.live_secret()
        self.user.is_active = False
        self.user.save()

        with self.assertRaises(InvalidPasswordSetToken):
            confirm_password_set(secret, NEW_PASSWORD)

    def test_unknown_secret_is_refused(self):
        with self.assertRaises(InvalidPasswordSetToken):
            confirm_password_set("not-a-real-token", NEW_PASSWORD)
        with self.assertRaises(InvalidPasswordSetToken):
            confirm_password_set("", NEW_PASSWORD)

    def test_weak_password_is_refused_and_leaves_the_link_live(self):
        secret = self.live_secret()

        with self.assertRaises(DjangoValidationError):
            confirm_password_set(secret, WEAK_PASSWORD)

        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())
        # The person can try again with a better password rather than being locked
        # out of a link they never managed to use.
        self.assertTrue(token_is_usable(secret))

    def test_password_similar_to_the_account_is_refused(self):
        secret = self.live_secret()

        with self.assertRaises(DjangoValidationError):
            confirm_password_set(secret, "new.employee@luanar.ac.mw")

    def test_confirm_is_audited(self):
        self.issue()
        confirm_password_set(self.secret_from_mail(), NEW_PASSWORD)

        entry = AuditEntry.objects.filter(action=AuditEntry.Action.PASSWORD_SET).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.target_type, AuditEntry.TargetType.USER_ACCOUNT)


class PasswordSetEndpointTests(PasswordSetBase):
    """The three public endpoints."""

    def live_secret(self) -> str:
        """A token that was just issued, read back out of the email body."""
        self.issue()
        return self.secret_from_mail()

    def setUp(self):
        super().setUp()
        self.client = APIClient()  # type: ignore[assignment]

    def test_request_returns_202_for_a_known_address(self):
        response = self.client.post(REQUEST_URL, {"email": self.user.email})

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(self.token_rows()), 1)

    def test_request_response_is_identical_for_an_unknown_address(self):
        known = self.client.post(REQUEST_URL, {"email": self.user.email})
        unknown = self.client.post(REQUEST_URL, {"email": "nobody@luanar.ac.mw"})

        # Byte-for-byte the same answer: this endpoint must not be an oracle for
        # "who works here".
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(NotificationOutbox.objects.count(), 1)

    def test_request_rejects_a_malformed_address(self):
        response = self.client.post(REQUEST_URL, {"email": "not-an-address"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_is_throttled(self):
        for _ in range(5):
            self.client.post(REQUEST_URL, {"email": self.user.email})

        response = self.client.post(REQUEST_URL, {"email": self.user.email})

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_validate_reports_a_live_token(self):
        secret = self.live_secret()

        response = self.client.get(VALIDATE_URL, {"token": secret})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["valid"], True)

    def test_validate_reports_a_dead_token_without_distinguishing_why(self):
        secret = self.live_secret()
        confirm_password_set(secret, NEW_PASSWORD)

        used = self.client.get(VALIDATE_URL, {"token": secret})
        unknown = self.client.get(VALIDATE_URL, {"token": "nonsense"})

        self.assertIs(used.data["valid"], False)
        self.assertEqual(used.data, unknown.data)

    def test_validate_requires_a_token(self):
        self.assertEqual(
            self.client.get(VALIDATE_URL).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_confirm_succeeds_and_does_not_hand_out_a_session(self):
        secret = self.live_secret()

        response = self.client.post(
            CONFIRM_URL, {"token": secret, "password": NEW_PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No auto-login: the caller already knows the password, so a session here
        # would only add a fixation surface.
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(list(mail.outbox), [])

    def test_confirm_with_a_dead_token_is_a_400_not_a_500(self):
        response = self.client.post(
            CONFIRM_URL, {"token": "nonsense", "password": NEW_PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no longer valid", str(response.data["detail"]))

    def test_confirm_reports_password_policy_failures(self):
        secret = self.live_secret()

        response = self.client.post(
            CONFIRM_URL, {"token": secret, "password": WEAK_PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())


class EmployeePasswordLinkTests(PasswordSetBase):
    """HR's side: the first link goes out automatically, resends on demand."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()  # type: ignore[assignment]
        self.list_url = "/api/v1/employees/"

    def payload(self, **overrides):
        body = {
            "email": "grace.hopper@luanar.ac.mw",
            "first_name": "Grace",
            "last_name": "Hopper",
            "designation": "Lecturer",
            "department": "Bunda College",
            "category": "academic",
            "grade": "C",
            "appointment_date": "2023-05-01",
        }
        body.update(overrides)
        return body

    def test_creating_an_employee_mails_a_set_password_link(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(self.list_url, self.payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="grace.hopper@luanar.ac.mw")
        self.assertEqual(
            list(NotificationOutbox.objects.filter(user=created)), list(
                NotificationOutbox.objects.filter(user=created)
            )
        )
        row = NotificationOutbox.objects.get(user=created)
        self.assertEqual(row.kind, "password_set")
        self.assertEqual(row.recipient_email, created.email)
        self.assertEqual(
            PasswordSetToken.objects.filter(user=created, issued_by=self.hr_user).count(),
            1,
        )
        self.assertIsNotNone(created.employee_profile)

    def test_creating_an_employee_does_not_reuse_the_old_outbox_rows(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(self.list_url, self.payload(email="second@luanar.ac.mw"))

        rows = NotificationOutbox.objects.filter(
            user__email="second@luanar.ac.mw", kind="password_set"
        )

        self.assertEqual(rows.count(), 1)

    def test_attaching_an_existing_able_account_does_not_mail_a_link(self):
        existing = User.objects.create_user(
            username="already@luanar.ac.mw",
            email="already@luanar.ac.mw",
            password=NEW_PASSWORD,
            first_name="Already",
            last_name="Set",
        )
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(
            self.list_url,
            self.payload(
                email="already@luanar.ac.mw",
                first_name="Already",
                last_name="Set",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(existing.employee_profile, EmployeeProfile.objects.get(user=existing))
        # Somebody who already has a password must never be mailed a reset link
        # just because HR attached an employee record to them.
        self.assertEqual(NotificationOutbox.objects.filter(user=existing).count(), 0)

    def test_hr_can_resend_the_link(self):
        self.client.force_authenticate(user=self.hr_user)
        self.client.post(self.list_url, self.payload())
        created = User.objects.get(email="grace.hopper@luanar.ac.mw")
        first_secret = (
            NotificationOutbox.objects.get(user=created).body.split("?token=")[1].split()[0]
        )

        response = self.client.post(
            f"{self.list_url}{created.employee_profile.pk}/password-set-link/",
            {},
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(NotificationOutbox.objects.filter(user=created).count(), 2)
        self.assertFalse(token_is_usable(first_secret))
        self.assertEqual(
            PasswordSetToken.objects.filter(user=created).count(), 2
        )

    def test_resend_is_refused_for_an_account_without_an_email(self):
        profile = EmployeeProfile.objects.create(user=self.user)
        self.user.email = ""
        self.user.save()
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(
            f"{self.list_url}{profile.pk}/password-set-link/", {}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no email address", str(response.data["detail"]))

    def test_resend_is_refused_for_a_deactivated_account(self):
        profile = EmployeeProfile.objects.create(user=self.user)
        self.user.is_active = False
        self.user.save()
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(
            f"{self.list_url}{profile.pk}/password-set-link/", {}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deactivated", str(response.data["detail"]))

    def test_an_ordinary_employee_cannot_resend_someone_elses_link(self):
        profile = EmployeeProfile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.hr_user)
        created = self.client.post(
            f"{self.list_url}{profile.pk}/password-set-link/", {}
        )
        self.assertEqual(created.status_code, status.HTTP_202_ACCEPTED)

        attacker = User.objects.create_user(
            username="attacker@luanar.ac.mw",
            email="attacker@luanar.ac.mw",
            password=NEW_PASSWORD,
        )
        self.client.force_authenticate(user=attacker)

        response = self.client.post(
            f"{self.list_url}{profile.pk}/password-set-link/", {}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_form_encoded_create_still_produces_an_active_account(self):
        """Regression: DRF reads an absent boolean in a form body as False.

        Any form-encoded client — ``curl -F``, an HTML form, DRF's own test
        client — omits ``is_active`` entirely, and ``BooleanField`` supplies
        False for HTML input. The account was therefore created deactivated,
        which looks like an HR mistake and is not one.
        """
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(
            self.list_url, self.payload(), format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="grace.hopper@luanar.ac.mw")
        self.assertTrue(created.is_active)
        # Active is not enough: the link has to have gone out, or HR is back to
        # typing passwords into admin.
        self.assertEqual(NotificationOutbox.objects.filter(user=created).count(), 1)

    def test_an_explicitly_deactivated_create_is_honoured_and_not_emailed(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.post(
            self.list_url, self.payload(is_active=False), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="grace.hopper@luanar.ac.mw")
        self.assertFalse(created.is_active)
        # No point mailing a link to an account that cannot sign in with it.
        self.assertEqual(NotificationOutbox.objects.filter(user=created).count(), 0)


class RetireDemoUsersCommandTests(TestCase):
    """The demo accounts go quiet; their history stays put."""

    def setUp(self):
        self.demo = User.objects.create_user(
            username="employee@test.luanar",
            email="employee@test.luanar",
            password="testpass123",
            first_name="Test",
            last_name="Employee",
        )
        self.real = User.objects.create_user(
            username="real.person@luanar.ac.mw",
            email="real.person@luanar.ac.mw",
            password="Str0ng!pass99",
            first_name="Real",
            last_name="Person",
        )
        self.history = AuditEntry.objects.create(
            actor=self.demo,
            action=AuditEntry.Action.SUBMITTED,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=self.demo.pk,
            target_summary=self.demo.get_full_name(),
        )

    def test_demo_accounts_are_deactivated_and_stripped(self):
        call_command("retire_demo_users", stdout=StringIO())

        self.demo.refresh_from_db()
        self.assertFalse(self.demo.is_active)
        self.assertFalse(self.demo.has_usable_password())
        self.assertIsNone(
            authenticate(username="employee@test.luanar", password="testpass123")
        )

    def test_a_real_account_is_left_alone(self):
        call_command("retire_demo_users", stdout=StringIO())

        self.real.refresh_from_db()
        self.assertTrue(self.real.is_active)
        self.assertTrue(self.real.has_usable_password())

    def test_history_is_untouched(self):
        call_command("retire_demo_users", stdout=StringIO())

        # The protected reference that makes deleting the account impossible is
        # still there, and readable.
        self.assertTrue(
            AuditEntry.objects.filter(pk=self.history.pk)
            .select_related("actor")
            .exists()
        )

    def test_deleting_the_account_instead_is_refused(self):
        """The reason this command deactivates rather than deletes."""
        with self.assertRaises(ProtectedError):
            User.objects.filter(pk=self.demo.pk).delete()

    def test_the_change_is_audited_with_no_actor(self):
        call_command("retire_demo_users", stdout=StringIO())

        entry = AuditEntry.objects.filter(
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.USER_ACCOUNT,
        ).get()
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.detail["source"], "retire_demo_users")

    def test_running_it_twice_changes_nothing_the_second_time(self):
        call_command("retire_demo_users", stdout=StringIO())
        call_command("retire_demo_users", stdout=StringIO())

        self.assertEqual(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.DEACTIVATED,
                target_type=AuditEntry.TargetType.USER_ACCOUNT,
            ).count(),
            1,
        )

    def test_undo_restores_the_seeded_state(self):
        call_command("retire_demo_users", stdout=StringIO())
        call_command("retire_demo_users", "--undo", stdout=StringIO())

        self.demo.refresh_from_db()
        self.assertTrue(self.demo.is_active)
        self.assertIsNotNone(
            authenticate(username="employee@test.luanar", password="testpass123")
        )

class NoDemoAccountsTests(TestCase):
    """A database that never had the seed command run."""

    def test_it_reports_nothing_to_do(self):
        User.objects.create_user(
            username="real.person@luanar.ac.mw",
            email="real.person@luanar.ac.mw",
            password="Str0ng!pass99",
        )

        out = StringIO()
        call_command("retire_demo_users", stdout=out)

        self.assertIn("nothing to do", out.getvalue())
