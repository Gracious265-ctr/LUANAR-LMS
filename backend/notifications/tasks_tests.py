"""Transport-level behaviour of the delivery task (the only ``send_mail`` call site).

The composers' tests prove a *queue call* writes the right rows; these tests
prove what happens when a worker picks one up: which address the mail goes to,
which ``From:`` it carries, and what the row records when the relay or the broker
is unavailable.

A delegation is used as the subject because it is the cheapest outbox subject
that satisfies the one-subject constraint.
"""

from __future__ import annotations

from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.models import NotificationOutbox
from notifications.tasks import _from_email, deliver_notification, enqueue_delivery
from org.models import Delegation
from workflows.testing import make_approver

DELIVERY_TASK = "notifications.tasks.deliver_notification"


class DeliveryTaskTests(TestCase):
    def setUp(self):
        self.dean = make_approver("dean", username="dean@tasks.test")
        self.delegation = Delegation.objects.create(
            approver=self.dean,
            starts_on=timezone.localdate(),
            requested_by=self.dean,
            status=Delegation.Status.REQUESTED,
        )
        self.row = NotificationOutbox.objects.create(
            delegation=self.delegation,
            kind="delegation_requested",
            role_label="delegate",
            recipient_email="hod@tasks.test",
            subject="Delegation requested",
            body="Please review.",
        )

    # --- recipients -------------------------------------------------------

    @override_settings(
        DEBUG=True, EMAIL_DEV_RECIPIENT_OVERRIDE=["ops@luanar.ac.mw"]
    )
    def test_the_debug_override_routes_mail_into_one_inbox(self):
        state = deliver_notification(
            self.row.pk, recipients=["hod@tasks.test", "dean@tasks.test"]
        )

        self.assertEqual(state, "sent")
        self.assertEqual(mail.outbox[0].to, ["ops@luanar.ac.mw"])
        self.row.refresh_from_db()
        # The row still records who the mail was *about*; only delivery moves.
        self.assertEqual(self.row.recipient_email, "hod@tasks.test")

    @override_settings(
        DEBUG=False, EMAIL_DEV_RECIPIENT_OVERRIDE=["ops@luanar.ac.mw"]
    )
    def test_the_override_is_refused_when_debug_is_off(self):
        """A wrong recipient must never be masked in production."""
        with self.assertLogs("notifications.tasks", level="ERROR") as logs:
            state = deliver_notification(
                self.row.pk, recipients=["hod@tasks.test", "dean@tasks.test"]
            )

        self.assertEqual(state, "sent")
        self.assertEqual(mail.outbox[0].to, ["hod@tasks.test", "dean@tasks.test"])
        self.assertIn("DEBUG is off", "\n".join(logs.output))

    @override_settings(DEBUG=True, EMAIL_DEV_RECIPIENT_OVERRIDE=[])
    def test_no_override_leaves_the_real_recipients_alone(self):
        deliver_notification(self.row.pk, recipients=["hod@tasks.test"])

        self.assertEqual(mail.outbox[0].to, ["hod@tasks.test"])

    def test_the_row_recipient_is_the_fallback(self):
        deliver_notification(self.row.pk)

        self.assertEqual(mail.outbox[0].to, ["hod@tasks.test"])

    # --- From: header -----------------------------------------------------

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="",
    )
    def test_smtp_without_a_default_from_email_records_failed(self):
        """Gmail rejects an unauthorised ``From:``; say so on the row."""
        state = deliver_notification(self.row.pk)

        self.assertEqual(state, "failed")
        self.row.refresh_from_db()
        self.assertIn("DEFAULT_FROM_EMAIL", self.row.error)
        self.assertEqual(mail.outbox, [])

    @override_settings(DEFAULT_FROM_EMAIL="notifications@luanar.ac.mw")
    def test_the_configured_from_address_is_used(self):
        deliver_notification(self.row.pk)

        self.assertEqual(mail.outbox[0].from_email, "notifications@luanar.ac.mw")

    @override_settings(DEFAULT_FROM_EMAIL="")
    def test_the_console_backend_falls_back_to_the_no_reply_sender(self):
        self.assertEqual(_from_email(), "no-reply@luanar.ac.mw")

        deliver_notification(self.row.pk)
        self.assertEqual(mail.outbox[0].from_email, "no-reply@luanar.ac.mw")

    # --- state machine ----------------------------------------------------

    def test_a_missing_row_is_reported_not_raised(self):
        self.assertEqual(deliver_notification(999999), "missing")

    def test_a_sent_row_is_never_resent(self):
        deliver_notification(self.row.pk)
        with mock.patch("notifications.tasks.send_mail") as send:
            self.assertEqual(deliver_notification(self.row.pk), "sent")
        send.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)

    def test_a_failed_row_is_not_retried(self):
        with mock.patch(
            "notifications.tasks.send_mail", side_effect=OSError("relay down")
        ):
            self.assertEqual(deliver_notification(self.row.pk), "failed")

        with mock.patch("notifications.tasks.send_mail") as send:
            self.assertEqual(deliver_notification(self.row.pk), "failed")
        send.assert_not_called()
        self.row.refresh_from_db()
        self.assertEqual(self.row.state, "failed")
        self.assertIn("relay down", self.row.error)

    # --- dispatch ---------------------------------------------------------

    @override_settings(NOTIFICATIONS_SYNC_SEND=False)
    def test_enqueue_hands_the_task_the_full_recipient_list(self):
        with mock.patch("django_q.tasks.async_task") as async_task:
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_delivery(
                    self.row, ["hod@tasks.test", "dean@tasks.test"]
                )

        async_task.assert_called_once_with(
            DELIVERY_TASK, self.row.pk, ["hod@tasks.test", "dean@tasks.test"], sync=False
        )
        self.row.refresh_from_db()
        self.assertEqual(self.row.state, "pending")

    @override_settings(NOTIFICATIONS_SYNC_SEND=False)
    def test_a_dead_broker_leaves_the_row_pending_and_raises_nothing(self):
        with mock.patch(
            "django_q.tasks.async_task", side_effect=OSError("broker unreachable")
        ):
            with self.assertLogs("notifications.tasks", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    enqueue_delivery(self.row, ["hod@tasks.test"])

        self.row.refresh_from_db()
        self.assertEqual(self.row.state, "pending")
        self.assertEqual(mail.outbox, [])

    @override_settings(NOTIFICATIONS_SYNC_SEND=True)
    def test_sync_send_delivers_inline_without_a_worker(self):
        """The single-process development path: no qcluster required."""
        with self.captureOnCommitCallbacks(execute=True):
            enqueue_delivery(self.row, ["hod@tasks.test"])

        self.row.refresh_from_db()
        self.assertEqual(self.row.state, "sent")
        self.assertEqual(mail.outbox[0].to, ["hod@tasks.test"])

    def test_nothing_is_dispatched_before_the_commit(self):
        with mock.patch("django_q.tasks.async_task") as async_task:
            enqueue_delivery(self.row, ["hod@tasks.test"])

        async_task.assert_not_called()
        self.assertEqual(
            NotificationOutbox.objects.filter(state="pending").count(),
            1,
            "the row stays pending until a worker or the commit dispatches it",
        )
