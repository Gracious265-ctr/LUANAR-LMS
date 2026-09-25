"""Unit 22 — decision-email consumer on the Unit 16 approval bus.

Discipline (mirrors Unit 16 D1 / Unit 18):

* A real ``LeaveApplication`` row is created by hand — the same seam every other
  leave/workflow test uses (``LeaveApplication.objects.create`` with an owner).
* A decision is emitted through ``workflows.events.emit_approval_event`` — the
  exact Unit-16 bus and its consumer registry; no bespoke fake bus.
* Assertions read the durable truth, the append-only ``NotificationOutbox``
  rows, plus the console backend's ``mail.outbox``.
* Each ``(application, kind, submission_cycle, role_label)`` maps to exactly one
  outbox row — enforced by the unique constraint + ``get_or_create``.
"""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
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
    send_decision_email,
)
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
        register_consumer(send_decision_email)
        self.employee = self._make_user("employee@test.luanar")
        self.approver = self._make_user("approver@test.luanar", role=User.Role.HOD)
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
        return User.objects.create_user(
            username=f"user-{uuid4().hex[:8]}",
            email=email,
            password="testpass123",
            role=role,
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

    def test_decision_creates_one_outbox_row_sent_to_owner(self):
        emit_approval_event(self._event())

        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.kind, DECISION_RECORDED)
        self.assertEqual(row.state, "sent")
        self.assertIsNotNone(row.sent_at)
        self.assertEqual(row.recipient_email, self.employee.email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.employee.email])
        self.assertIn(self.application.reference_number, mail.outbox[0].subject)

    def test_double_emit_is_idempotent(self):
        emit_approval_event(self._event())
        emit_approval_event(self._event())  # re-broadcast must not duplicate

        self.assertEqual(
            NotificationOutbox.objects.filter(application=self.application).count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_outbox_is_append_only(self):
        emit_approval_event(self._event())
        row = NotificationOutbox.objects.get(application=self.application)
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).update(state="pending")
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).delete()

    def test_finalised_includes_approver(self):
        emit_approval_event(self._event(kind=APPLICATION_FINALISED, action="approve"))

        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.kind, APPLICATION_FINALISED)
        self.assertEqual(
            mail.outbox[0].to, [self.employee.email, self.approver.email]
        )

    def test_send_failure_records_failed_and_isolates(self):
        with mock.patch(
            "notifications.services.send_mail",
            side_effect=RuntimeError("smtp down"),
        ):
            emit_approval_event(self._event())

        row = NotificationOutbox.objects.get(application=self.application)
        self.assertEqual(row.state, "failed")
        self.assertIn("smtp down", row.error)

    def test_consumer_exception_does_not_abort_siblings_or_commit(self):
        def boom(event):
            raise RuntimeError("bad consumer")

        register_consumer(boom)
        emit_approval_event(self._event())  # must not raise

        self.assertEqual(
            NotificationOutbox.objects.filter(application=self.application).count(),
            1,
        )

    def test_missing_application_raises_unresolvable(self):
        event = self._event()
        object.__setattr__(event, "application_id", str(uuid4()))

        with self.assertRaises(NotificationSeamUnresolvableError):
            send_decision_email(event)
