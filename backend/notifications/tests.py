"""Unit 22 — decision-email consumer on the Unit 16 approval bus.

Discipline (mirrors Unit 16 D1 / Unit 18):

* A real ``LeaveApplication`` row is created by hand — the same seam every other
  leave/workflow test uses (``LeaveApplication.objects.create`` with an owner).
* A decision is emitted through ``workflows.events.emit_approval_event`` — the
  exact Unit-16 bus and its consumer registry; no bespoke fake bus.
* Assertions read the durable truth, the append-only ``NotificationOutbox``
  rows, plus the locmem backend's ``mail.outbox``.
* Delivery is queued, so a test asserts the two halves separately: the emit
  leaves a ``pending`` row and hands the delivery to django-q2
  (``async_task`` patched, as the documents suite does), and
  ``notifications.tasks.deliver_notification`` is then run directly — the same
  split ``config.settings.test`` documents when it pins ``sync = False``.
* Each ``(application, kind, submission_cycle, role_label)`` maps to exactly one
  outbox row — enforced by the unique constraint + ``get_or_create``.
"""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model

from workflows.testing import create_user_with_role
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from leave.models import LeaveApplication
from notifications.models import (
    NotificationOutbox,
    NotificationOutboxLockedError,
)
from notifications.services import (
    NotificationSeamUnresolvableError,
    queue_decision_email,
)
from notifications.tasks import deliver_notification
from workflows.events import (
    APPLICATION_FINALISED,
    DECISION_RECORDED,
    ApprovalEvent,
    _reset_consumers_for_tests,
    emit_approval_event,
    register_consumer,
)

User = get_user_model()


class DecisionEmailBusTest(TestCase):
    """The Unit 22 bus turns one decision into exactly one outbox email."""

    def setUp(self):
        _reset_consumers_for_tests()
        register_consumer(queue_decision_email)
        self.employee = self._make_user("employee@test.luanar")
        self.approver = self._make_user("approver@test.luanar", role="hod")
        self.application = LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number=f"LV-{uuid4().hex[:12]}",
            submission_cycle=1,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            reason="Family emergency",
            submitted_at=timezone.now(),
        )

    def _make_user(self, email, role=User.Role.EMPLOYEE):
        """Create an account; an approver role code also gets a real holding."""
        return create_user_with_role(
            f"user-{uuid4().hex[:8]}", email=email, role=role
        )

    def _event(self, kind=DECISION_RECORDED, action="approve"):
        return ApprovalEvent(
            kind=kind,
            application_id=str(self.application.pk),
            reference_number=self.application.reference_number,
            action=action,
            stage_order=1,
            role_label="supervisor",
            approver_id=self.approver.id,
            approver_name=self.approver.get_full_name(),
            comment="Approved in Unit 22",
            submission_cycle=1,
        )

    def _emit(self, event):
        """Emit on the bus with the commit honoured; return the enqueue mock.

        ``async_task`` is patched so the suite never writes to the django-q ORM
        broker. Delivery is then run explicitly by the test.
        """
        with mock.patch("django_q.tasks.async_task") as async_task:
            with self.captureOnCommitCallbacks(execute=True):
                emit_approval_event(event)
        return async_task

    def _deliver(self, row, recipients=None):
        return deliver_notification(row.pk, recipients=recipients)

    def test_decision_records_one_pending_row_and_queues_one_delivery(self):
        async_task = self._emit(self._event())

        async_task.assert_called_once()
        self.assertEqual(
            async_task.call_args.args[0], "notifications.tasks.deliver_notification"
        )
        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.kind, DECISION_RECORDED)
        self.assertEqual(row.state, "pending")
        self.assertIsNone(row.sent_at)
        # The full recipient list travels with the task: re-deriving it from the
        # row would silently drop the finalising approver.
        self.assertEqual(async_task.call_args.args[2], [self.employee.email])

    def test_delivery_sends_to_the_owner_and_marks_the_row_sent(self):
        self._emit(self._event())

        self.assertEqual(self._deliver(row_for(self.application)), "sent")

        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.state, "sent")
        self.assertIsNotNone(row.sent_at)
        self.assertEqual(row.error, "")
        self.assertEqual(row.recipient_email, self.employee.email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.employee.email])
        self.assertIn(self.application.reference_number, mail.outbox[0].subject)

    def test_double_emit_is_idempotent(self):
        self._emit(self._event())
        self._emit(self._event())  # re-broadcast must not duplicate

        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(self._deliver(row), "sent")
        self.assertEqual(
            NotificationOutbox.objects.filter(application=self.application).count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_delivering_twice_sends_once(self):
        self._emit(self._event())
        row = NotificationOutbox.objects.get(application=self.application)

        self.assertEqual(self._deliver(row), "sent")
        # A worker restart or a retried task must not repeat the mail.
        self.assertEqual(self._deliver(row), "sent")
        self.assertEqual(len(mail.outbox), 1)

    def test_outbox_is_append_only(self):
        self._emit(self._event())
        row = NotificationOutbox.objects.get(application=self.application)
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).update(state="pending")
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).delete()

    def test_finalised_reaches_the_owner_and_the_finalising_approver(self):
        self._emit(self._event(kind=APPLICATION_FINALISED, action="approve"))
        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.kind, APPLICATION_FINALISED)

        deliver_notification(
            row.pk, recipients=[self.employee.email, self.approver.email]
        )

        self.assertEqual(
            mail.outbox[0].to, [self.employee.email, self.approver.email]
        )

    def test_delivery_failure_records_failed_and_isolates(self):
        self._emit(self._event())
        row = NotificationOutbox.objects.get(application=self.application)

        with mock.patch(
            "notifications.tasks.send_mail",
            side_effect=RuntimeError("smtp down"),
        ):
            self.assertEqual(self._deliver(row), "failed")

        row.refresh_from_db()
        self.assertEqual(row.state, "failed")
        self.assertIn("smtp down", row.error)
        self.assertIsNone(row.sent_at)
        # The decision itself is untouched by a dead relay.
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, LeaveApplication.Status.SUBMITTED)

    def test_a_failed_row_is_not_retried_into_a_second_send(self):
        self._emit(self._event())
        row = NotificationOutbox.objects.get(application=self.application)
        with mock.patch("notifications.tasks.send_mail", side_effect=OSError("down")):
            self._deliver(row)

        self.assertEqual(self._deliver(row), "failed")
        self.assertEqual(len(mail.outbox), 0)

    def test_consumer_exception_does_not_abort_siblings_or_commit(self):
        def boom(event):
            raise RuntimeError("bad consumer")

        register_consumer(boom)
        self._emit(self._event())  # must not raise

        self.assertEqual(
            NotificationOutbox.objects.filter(application=self.application).count(),
            1,
        )

    def test_missing_application_raises_unresolvable(self):
        event = self._event()
        object.__setattr__(event, "application_id", str(uuid4()))

        with self.assertRaises(NotificationSeamUnresolvableError):
            queue_decision_email(event)


def row_for(application):
    """The one outbox row a single decision produces."""
    return NotificationOutbox.objects.get(application=application)
