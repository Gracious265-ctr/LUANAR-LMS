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