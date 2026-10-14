<<<<<<< HEAD
"""Unit 22 tests: email notifications.

Covers the ``Notification`` model + service (rows persisted, eligible
recipients only, one enqueue per row), the delivery task (sent/failed/no-SMTP
/rerun idempotency), the settings/config defaults, and the event wiring:
submission, approval decisions, cancellations (including
``employee_notification_state`` transitions), delegation and reassignment.

Domain events fire on ``transaction.on_commit``, which Django's ``TestCase``
suppresses, so every cross-cutting test wraps the command in
``self.captureOnCommitCallbacks(execute=True)`` to release the callbacks. Dispatch
is off in ``config/settings/test.py``; these tests enable it explicitly.
"""

from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from leave.cancellations.services import decide_cancellation, submit_cancellation
from leave.models import CancellationRequest, LeaveApplication
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    TODAY,
    make_approver_chain,
    make_user,
)
from leave.tests.test_cancellation import CancellationFixtureMixin
from users.models import User
from workflows.approval import decide
from workflows.events import ApprovalEvent
from workflows.models import ApplicationStage, Delegation
from workflows.providers import get_workflow_provider
from workflows.services import (
    approve_delegation,
    cancel_delegation,
    reassign_application,
    reject_delegation,
)
from workflows.tests_approvals import ApprovalFixtureMixin

from notifications.dispatcher import dispatch
from notifications.models import Notification
from notifications.services import send_notification
from notifications.tasks import deliver_notification


class DispatchTestCase(TestCase):
    """Base for tests that let the domain events reach the subscribers."""

    def enable_dispatch(self):
        return override_settings(NOTIFICATION_DISPATCHER="on")

    def mock_async_task(self):
        patcher = mock.patch("notifications.services.async_task")
        patcher.start()
        self.addCleanup(patcher.stop)

    def on_commit(self, fn):
        with self.captureOnCommitCallbacks(execute=True):
            return fn()


# --- model + service ------------------------------------------------------------

class NotificationServiceTests(TestCase):
    def setUp(self):
        self.recipient = make_user(username="svc-recipient@test.luanar")
        self.approver = make_user(username="svc-approver@test.luanar", role="hod")
        self.inactive = make_user(username="svc-inactive@test.luanar")
        self.inactive.is_active = False
        self.inactive.save(update_fields=["is_active"])
        self.no_email = User.objects.create_user(
            username="svc-noemail@test.luanar", email="", password="testpass123"
        )
        self.async_task = mock.patch("notifications.services.async_task").start()
        self.addCleanup(mock.patch.stopall)

    def test_persists_one_enqueued_row_per_eligible_recipient(self):
        application_id = uuid4()
        rows = send_notification(
            event_type="leave.application.submitted",
            recipients=[
                self.recipient,
                self.approver,
                self.inactive,
                self.no_email,
            ],
            subject="Subject",
            body="Body",
            application_id=application_id,
        )
        self.assertEqual(
            {row.recipient_id for row in rows},
            {self.recipient.pk, self.approver.pk},
        )
        for row in rows:
            self.assertEqual(row.channel, Notification.Channel.EMAIL)
            self.assertEqual(row.status, Notification.Status.ENQUEUED)
            self.assertEqual(row.application_id, application_id)
            self.assertEqual(row.email_to, row.recipient.email)
            self.assertEqual(row.attempts, 0)

    def test_one_async_enqueue_per_row(self):
        rows = send_notification(
            event_type="leave.application.submitted",
            recipients=[self.recipient, self.approver],
            subject="Subject",
            body="Body",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.async_task.call_count, 2)

    def test_sync_callbacks_receive_the_created_rows(self):
        seen = []
        rows = send_notification(
            event_type="leave.application.submitted",
            recipients=[self.recipient],
            subject="Subject",
            body="Body",
            send_sync_callbacks=(lambda created: seen.extend(created),),
        )
        self.assertEqual(seen, rows)

    def test_no_eligible_recipients_returns_empty(self):
        rows = send_notification(
            event_type="leave.application.submitted",
            recipients=[self.inactive, self.no_email],
            subject="Subject",
            body="Body",
        )
        self.assertEqual(rows, [])
        self.assertEqual(Notification.objects.count(), 0)


# --- delivery task ---------------------------------------------------------------

class DeliverNotificationTests(TestCase):
    def _notification(self, email_to="deliver@test.luanar"):
        recipient = make_user(username=email_to)
        return Notification.objects.create(
            event_type="approval.stage_assigned",
            recipient=recipient,
            email_to=recipient.email,
            subject="Approval required",
            body="Please approve.",
        )

    @override_settings(
        EMAIL_HOST_USER="tester@luanar.ac.mw",
        EMAIL_HOST_PASSWORD="secret",
    )
    def test_delivers_and_marks_sent(self):
        row = self._notification()
        status_result = deliver_notification(row.pk)
        row.refresh_from_db()
        self.assertEqual(status_result, Notification.Status.SENT)
        self.assertEqual(row.status, Notification.Status.SENT)
        self.assertEqual(row.attempts, 1)
        self.assertIsNotNone(row.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [row.email_to])
        self.assertEqual(mail.outbox[0].subject, "Approval required")

    @override_settings(
        EMAIL_HOST_USER="tester@luanar.ac.mw",
        EMAIL_HOST_PASSWORD="secret",
    )
    def test_rerun_of_sent_row_is_idempotent(self):
        row = self._notification()
        deliver_notification(row.pk)
        row.refresh_from_db()
        deliver_notification(row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, Notification.Status.SENT)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_marks_failed_when_smtp_not_configured(self):
        row = self._notification()
        with override_settings(EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD=""):
            deliver_notification(row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, Notification.Status.FAILED)
        self.assertIn("SMTP not configured", row.error)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_HOST_USER="tester@luanar.ac.mw",
        EMAIL_HOST_PASSWORD="secret",
    )
    def test_marks_failed_and_records_error_on_send_exception(self):
        row = self._notification()
        with mock.patch(
            "notifications.tasks.send_mail",
            side_effect=RuntimeError("SMTP connection refused"),
        ):
            deliver_notification(row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, Notification.Status.FAILED)
        self.assertEqual(row.error, "SMTP connection refused")
        self.assertEqual(row.attempts, 1)
        self.assertIsNone(row.sent_at)


# --- configuration / dispatcher --------------------------------------------------

class ConfigurationTests(TestCase):
    def test_dev_email_defaults_point_at_google_smtp(self):
        self.assertEqual(settings.EMAIL_HOST, "smtp.gmail.com")
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)
        self.assertEqual(settings.DEFAULT_FROM_EMAIL, "LUANAR Leave <noreply@luanar.ac.mw>")

    def test_test_settings_keep_dispatch_off_and_locmem(self):
        self.assertEqual(settings.NOTIFICATION_DISPATCHER, "off")
        self.assertEqual(
            settings.EMAIL_BACKEND,
            "django.core.mail.backends.locmem.EmailBackend",
        )

    def test_dispatch_has_no_return_side_effect(self):
        with override_settings(NOTIFICATION_DISPATCHER="off"):
            self.assertIsNone(dispatch("approval", object()))
        event = ApprovalEvent(
            kind="application_finalised",
            application_id=str(uuid4()),
            stage_order=1,
            action="approve",
            cycle=1,
            occurred_at=timezone.now(),
        )
        with override_settings(NOTIFICATION_DISPATCHER="on"):
            self.assertIsNone(dispatch("approval", event))


# --- event wiring: submission ----------------------------------------------------

class SubmissionNotificationTests(DispatchTestCase, StubProviderMixin):
    def setUp(self):
        self.stub = self.use_stub()
        chain = make_approver_chain()
        self.hod = chain["hod"]
        self.dean = chain["dean"]
        self.registrar = chain["registrar"]
        self.dvc = chain["dvc"]
        self.employee = make_user()
        self.stub.register_employee(self.employee)
        self.mock_async_task()

    def _submit(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=4),
            reason="Annual leave",
        )
        from leave.services.submission import submit_application

        self.on_commit(
            lambda: submit_application(user=self.employee, application_id=app.id)
        )
        app.refresh_from_db()
        return app

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_submission_notifies_employee_and_workflow_members(self):
        app = self._submit()
        rows = list(Notification.objects.filter(event_type="leave.application.submitted"))
        member_ids = set(get_workflow_provider().get_workflow_member_user_ids(app))
        self.assertEqual(
            {row.recipient_id for row in rows},
            {self.employee.id, *member_ids},
        )
        for row in rows:
            self.assertEqual(row.application_id, app.id)
            self.assertIn(
                "submitted",
                row.body,
            )


# --- event wiring: approval ------------------------------------------------------

class ApprovalNotificationTests(DispatchTestCase, ApprovalFixtureMixin):
    def setUp(self):
        super().setUpApprovals()
        self.mock_async_task()

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_submission_notifies_employee_and_members(self):
        with self.captureOnCommitCallbacks(execute=True):
            app = self.submit()
        rows = Notification.objects.filter(event_type="leave.application.submitted")
        member_ids = set(get_workflow_provider().get_workflow_member_user_ids(app))
        self.assertEqual(
            {row.recipient_id for row in rows},
            {self.employee.id, *member_ids},
        )

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_stage_assigned_notifies_the_next_approver(self):
        with self.captureOnCommitCallbacks(execute=True):
            app = self.submit()
        with self.captureOnCommitCallbacks(execute=True):
            self.advance(app, self.hod)
        pending = ApplicationStage.objects.get(
            application=app, status=ApplicationStage.Status.PENDING
        )
        rows = Notification.objects.filter(event_type="approval.stage_assigned")
        self.assertEqual(list(rows.values_list("recipient_id", flat=True)), [pending.assigned_approver_id])
        for row in rows:
            self.assertEqual(row.application_id, app.id)
            self.assertIn("approval", row.subject.lower())

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_reject_notifies_employee(self):
        with self.captureOnCommitCallbacks(execute=True):
            app = self.submit()
        stage = app.current_stage
        with self.captureOnCommitCallbacks(execute=True):
            decide(
                application_id=app.id,
                actor=self.hod,
                action="reject",
                comment="Expression review needed",
                expected_stage_version=stage.version,
            )
        rows = Notification.objects.filter(event_type="approval.decision_recorded")
        self.assertEqual(list(rows.values_list("recipient_id", flat=True)), [self.employee.id])
        self.assertIn("rejected", rows[0].subject.lower())

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_final_approval_notifies_employee(self):
        with self.captureOnCommitCallbacks(execute=True):
            app = self.submit()
            app = self.advance(app, self.hod, self.dean, self.registrar, self.dvc)
        rows = Notification.objects.filter(event_type="approval.application_finalised")
        self.assertEqual(list(rows.values_list("recipient_id", flat=True)), [self.employee.id])
        self.assertIn("approved", rows[0].subject.lower())


# --- event wiring: cancellation --------------------------------------------------

class CancellationNotificationTests(DispatchTestCase, CancellationFixtureMixin):
    def setUp(self):
        super().setUpCancellation()
        self.mock_async_task()

    def _approved_app(self):
        return self.make_approved_app(start_offset=14)

    def _submit_request(self, app):
        self.on_commit(
            lambda: submit_cancellation(
                user=self.employee,
                application_id=app.id,
                reason="I no longer need this leave.",
                confirm=True,
                expected_action="request",
            )
        )
        return CancellationRequest.objects.get(application=app)

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_request_notifies_workflow_members(self):
        app = self._approved_app()
        self._submit_request(app)
        rows = list(Notification.objects.filter(event_type="cancellation.requested"))
        member_ids = set(get_workflow_provider().get_workflow_member_user_ids(app))
        self.assertEqual({row.recipient_id for row in rows}, member_ids)
        self.assertNotIn(self.employee.id, {row.recipient_id for row in rows})

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_final_approval_notifies_employee_and_members_and_flips_state(self):
        app = self._approved_app()
        request_row = self._submit_request(app)
        self.on_commit(
            lambda: decide_cancellation(
                user=self.hod,
                request_id=request_row.id,
                decision="approve",
                comment="Approved.",
                stage_version=1,
            )
        )
        rows = list(Notification.objects.filter(event_type="cancellation.approved"))
        member_ids = set(get_workflow_provider().get_workflow_member_user_ids(app))
        self.assertEqual(
            {row.recipient_id for row in rows},
            member_ids | {self.employee.id},
        )
        request_row.refresh_from_db()
        self.assertEqual(
            request_row.employee_notification_state,
            CancellationRequest.EmployeeNotificationState.SENT,
        )

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_reject_notifies_employee_and_flips_state(self):
        app = self._approved_app()
        request_row = self._submit_request(app)
        self.on_commit(
            lambda: decide_cancellation(
                user=self.hod,
                request_id=request_row.id,
                decision="reject",
                comment="Not approved.",
                stage_version=1,
            )
        )
        rows = list(Notification.objects.filter(event_type="cancellation.rejected"))
        self.assertEqual([row.recipient_id for row in rows], [self.employee.id])
        request_row.refresh_from_db()
        self.assertEqual(
            request_row.employee_notification_state,
            CancellationRequest.EmployeeNotificationState.SENT,
        )


# --- event wiring: delegation ----------------------------------------------------

class DelegationNotificationTests(DispatchTestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr-n@test.luanar", email="hr-n@test.luanar",
            password="testpass123", role="hr",
        )
        self.dean = User.objects.create_user(
            username="dean-n@test.luanar", email="dean-n@test.luanar",
            password="testpass123", role="dean",
        )
        self.hod = User.objects.create_user(
            username="hod-n@test.luanar", email="hod-n@test.luanar",
            password="testpass123", role="hod",
        )
        self.mock_async_task()

    def _request(self, **kwargs):
        kwargs.setdefault("approver", self.dean)
        kwargs.setdefault("requested_by", self.dean)
        kwargs.setdefault("starts_on", timezone.localdate() + timedelta(days=1))
        kwargs.setdefault("ends_on", timezone.localdate() + timedelta(days=5))
        return Delegation.objects.create(**kwargs)

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_approve_notifies_approver_and_delegate(self):
        delegation = self._request()
        self.on_commit(
            lambda: approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": "Dean on travel"}
            )
        )
        rows = Notification.objects.filter(event_type="delegation.approved")
        self.assertEqual(
            {row.recipient_id for row in rows}, {self.dean.id, self.hod.id}
        )

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_reject_notifies_approver(self):
        delegation = self._request()
        self.on_commit(
            lambda: reject_delegation(
                delegation, self.hr, {"decision_reason": "Delegate unavailable"}
            )
        )
        rows = Notification.objects.filter(event_type="delegation.rejected")
        self.assertEqual(
            {row.recipient_id for row in rows}, {self.dean.id}
        )

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_cancel_notifies_approver_and_delegate(self):
        delegation = self._request(
            status=Delegation.Status.APPROVED,
            delegate=self.hod,
            starts_on=timezone.localdate() - timedelta(days=1),
        )
        self.on_commit(
            lambda: cancel_delegation(
                delegation, self.hr, {"decision_reason": "Delegate unavailable"}
            )
        )
        rows = Notification.objects.filter(event_type="delegation.cancelled")
        self.assertEqual(
            {row.recipient_id for row in rows}, {self.dean.id, self.hod.id}
        )


# --- event wiring: reassignment --------------------------------------------------

class ReassignmentNotificationTests(DispatchTestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr-r@test.luanar", email="hr-r@test.luanar",
            password="testpass123", role="hr",
        )
        self.employee = User.objects.create_user(
            username="emp-r@test.luanar", email="emp-r@test.luanar",
            password="testpass123", role="employee",
        )
        self.dean = User.objects.create_user(
            username="dean-r@test.luanar", email="dean-r@test.luanar",
            password="testpass123", role="dean",
        )
        self.mock_async_task()

    def _submitted_app(self):
        return LeaveApplication.objects.create(
            employee=self.employee,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LV-2026-UNIT22",
            start_date=TODAY + timedelta(days=7),
            end_date=TODAY + timedelta(days=14),
            calculated_days=7,
            reason="Family emergency",
        )

    @override_settings(NOTIFICATION_DISPATCHER="on")
    def test_reassign_notifies_new_approver_and_employee(self):
        app = self._submitted_app()
        self.on_commit(
            lambda: reassign_application(
                application=app,
                to_approver=self.dean,
                actor=self.hr,
                reason="Dean took over",
            )
        )
        rows = list(Notification.objects.filter(event_type="reassignment.created"))
        self.assertEqual(
            {row.recipient_id for row in rows}, {self.dean.id, self.employee.id}
        )
        for row in rows:
            self.assertEqual(row.application_id, app.id)
            self.assertIn("reassigned", row.body.lower())
=======
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
>>>>>>> feature/plans-teams
