"""Cancellation-request emails.

The same discipline as :mod:`notifications.tests_delegations`, applied to the
cancellation subject family: a real ``CancellationRequest`` produced by the real
services (which broadcast on commit), asserted against the durable outbox rows and
the locmem ``mail.outbox``.

These tests are also the only place that pins the reconciliation between the outbox
row (the delivery record) and ``employee_notification_state`` (what the product
surfaces), because the cancellation composer is the only subject family that keeps
both.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase

from leave.cancellations.models import CancellationRequest
from leave.cancellations.services import (
    DECISION_APPROVE,
    DECISION_REJECT,
    decide_cancellation,
    submit_cancellation,
)
from leave.models import LeaveApplication
from leave.services.submission import submit_application
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    TODAY,
    StubProviderMixin,
    ensure_annual_leave_rule,
    make_user,
)
from notifications.cancellations import (
    KIND_CANCELLATION_APPROVED,
    KIND_CANCELLATION_REJECTED,
    KIND_CANCELLATION_REQUESTED,
    KIND_CANCELLATION_STAGE_APPROVED,
    KIND_CANCELLATION_WITHDRAWN,
    ROLE_EMPLOYEE,
    queue_cancellation_email,
)
from notifications.models import NotificationOutbox
from notifications.tasks import deliver_notification

ANNUAL = {
    "leave_type_id": 1,
    "start_date": EARLIEST_ANNUAL_START,
    "reason": "Family visit",
}


class CancellationEmailBase(StubProviderMixin, TestCase):
    """A real submitted application and a real approved one with a chain.

    Every service call goes through ``captureOnCommitCallbacks(execute=True)``:
    the cancellation bus broadcasts on commit, so without it the consumers never
    run and nothing lands in the outbox.
    """

    def setUp(self):
        # The application is built directly, so balance restoration resolves
        # through the current leave rule rather than a submission snapshot.
        ensure_annual_leave_rule()
        self.stub = self.use_stub()
        self.employee = make_user(
            "employee@notify.test", first_name="Ken", last_name="Employee"
        )
        self.supervisor = make_user(
            "supervisor@notify.test", role="supervisor", first_name="Sana"
        )
        self.hod = make_user("hod@notify.test", role="hod", first_name="Hady")
        self.stub.workflow.register_approver("supervisor", self.supervisor)
        self.stub.workflow.register_approver("hod", self.hod)
        self.stub.register_employee(self.employee)
        # The queue step must not reach a real broker; dispatch is stubbed and
        # asserted where it matters.
        self.async_task = mock.patch("django_q.tasks.async_task").start()
        self.addCleanup(self.async_task.stop)

    # --- fixtures ---------------------------------------------------------

    def make_submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def make_approved(self):
        from approvals.services import assign_workflow

        start = TODAY + timedelta(days=15)
        app = LeaveApplication.objects.create(
            employee=self.employee,
            start_date=start,
            end_date=start + timedelta(days=3),
            working_days=5,
            calendar_days=7,
            financial_year_label="2026-27",
            leave_type_id=1,
            reason="Family visit",
            status=LeaveApplication.Status.APPROVED,
        )
        assign_workflow(app)
        return app

    # --- service calls, each broadcasting on commit -----------------------

    def withdraw(self, app, reason="I no longer need this leave"):
        with self.captureOnCommitCallbacks(execute=True):
            return submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason=reason,
                confirm=True,
                expected_action="withdraw",
                today=TODAY,
            )

    def request_cancellation(self, app, reason="Plans changed"):
        with self.captureOnCommitCallbacks(execute=True):
            return submit_cancellation(
                user=self.employee,
                application_id=app.pk,
                reason=reason,
                confirm=True,
                expected_action="request",
                today=TODAY,
            )

    def decide(self, request, *, user=None, decision, comment="", stage_version):
        with self.captureOnCommitCallbacks(execute=True):
            return decide_cancellation(
                user=user or self.supervisor,
                request_id=request.pk,
                decision=decision,
                comment=comment,
                stage_version=stage_version,
                today=TODAY,
            )

    def approve_first_stage(self, request):
        return self.decide(
            request, decision=DECISION_APPROVE, comment="", stage_version=1
        )

    # --- outbox helpers ---------------------------------------------------

    def rows(self, request):
        return list(
            NotificationOutbox.objects.filter(cancellation=request).order_by(
                "created_at", "kind"
            )
        )

    def deliver_all(self, request):
        rows = self.rows(request)
        for row in rows:
            deliver_notification(row.pk, recipients=[row.recipient_email])
            row.refresh_from_db()  # the task marks its own copy, not this one
        return rows


class WithdrawalEmailTests(CancellationEmailBase):
    def test_a_withdrawal_queues_one_row_for_the_employee(self):
        app = self.make_submitted()

        request = self.withdraw(app)

        rows = self.rows(request)
        self.assertEqual([row.kind for row in rows], [KIND_CANCELLATION_WITHDRAWN])
        self.assertEqual(rows[0].recipient_email, self.employee.email)
        self.assertEqual(rows[0].role_label, ROLE_EMPLOYEE)
        self.assertEqual(rows[0].state, "pending", "queued, not sent inline")
        request.refresh_from_db()
        self.assertEqual(
            request.employee_notification_state,
            CancellationRequest.NotificationState.PENDING,
        )

    def test_the_queued_row_is_handed_to_the_delivery_task(self):
        app = self.make_submitted()

        request = self.withdraw(app)

        self.async_task.assert_called_once_with(
            "notifications.tasks.deliver_notification",
            self.rows(request)[0].pk,
            [self.employee.email],
            sync=False,
        )

    def test_the_withdrawal_email_reaches_the_employee_once_delivered(self):
        app = self.make_submitted()

        request = self.withdraw(app)
        rows = self.deliver_all(request)

        self.assertEqual([row.state for row in rows], ["sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(app.reference_number, mail.outbox[0].subject)
        self.assertIn("withdrawn", mail.outbox[0].body.lower())
        request.refresh_from_db()
        self.assertEqual(
            request.employee_notification_state,
            CancellationRequest.NotificationState.SENT,
        )

    def test_a_dead_relay_leaves_both_the_row_and_the_request_failed(self):
        app = self.make_submitted()
        request = self.withdraw(app)

        with mock.patch(
            "notifications.tasks.send_mail", side_effect=OSError("relay down")
        ):
            rows = self.deliver_all(request)

        self.assertEqual([row.state for row in rows], ["failed"])
        self.assertIn("relay down", rows[0].error)
        request.refresh_from_db()
        self.assertEqual(
            request.employee_notification_state,
            CancellationRequest.NotificationState.FAILED,
        )
        # The cancellation itself stands regardless of the mail.
        self.assertEqual(request.status, CancellationRequest.Status.APPROVED)


class CancellationRequestEmailTests(CancellationEmailBase):
    def test_requesting_cancellation_queues_one_row_for_the_employee(self):
        app = self.make_approved()

        request = self.request_cancellation(app)

        rows = self.rows(request)
        self.assertEqual([row.kind for row in rows], [KIND_CANCELLATION_REQUESTED])
        self.assertIn("approvers", rows[0].body)

    def test_a_stage_approval_queues_a_second_row_and_keeps_the_request_open(self):
        app = self.make_approved()
        request = self.request_cancellation(app)

        self.approve_first_stage(request)

        rows = self.rows(request)
        self.assertEqual(
            [row.kind for row in rows],
            [KIND_CANCELLATION_REQUESTED, KIND_CANCELLATION_STAGE_APPROVED],
        )
        self.assertIn("remaining approvers", rows[1].body)
        self.assertIn(f"Decided by: {self.supervisor.get_full_name()}", rows[1].body)

    def test_final_approval_email_states_the_restored_balance(self):
        app = self.make_approved()
        request = self.request_cancellation(app)
        self.approve_first_stage(request)
        decided = self.decide(
            request,
            user=self.hod,
            decision=DECISION_APPROVE,
            comment="Approved.",
            stage_version=2,
        )

        rows = self.deliver_all(decided)

        self.assertEqual(
            [row.kind for row in rows],
            [
                KIND_CANCELLATION_REQUESTED,
                KIND_CANCELLATION_STAGE_APPROVED,
                KIND_CANCELLATION_APPROVED,
            ],
        )
        self.assertEqual({row.state for row in rows}, {"sent"})
        self.assertEqual(len(mail.outbox), 3)
        approved_mail = next(
            m for m in mail.outbox if "\nOutcome: Cancellation approved\n" in m.body
        )
        self.assertIn("Restored to your leave balance", approved_mail.body)
        self.assertIn("Decided by:", approved_mail.body)
        self.assertIn(app.start_date.isoformat(), approved_mail.body)
        decided.refresh_from_db()
        self.assertEqual(
            decided.employee_notification_state,
            CancellationRequest.NotificationState.SENT,
        )

    def test_a_rejection_email_says_the_dates_are_unchanged(self):
        app = self.make_approved()
        request = self.request_cancellation(app)

        rejected = self.decide(
            request,
            decision=DECISION_REJECT,
            comment="Not enough notice.",
            stage_version=1,
        )

        rows = self.rows(rejected)
        self.assertEqual(
            [row.kind for row in rows],
            [KIND_CANCELLATION_REQUESTED, KIND_CANCELLATION_REJECTED],
        )
        self.assertIn("left unchanged", rows[1].body)
        self.assertIn("Decision note: Not enough notice.", rows[1].body)


class CancellationNotificationWiringTests(CancellationEmailBase):
    """The composer is really on the cancellation bus, and only once."""

    def test_the_bus_has_exactly_one_cancellation_consumer(self):
        from leave.cancellations import events

        consumers = [c for c in events._consumers if "cancellation" in c.__module__]
        self.assertEqual(consumers, [queue_cancellation_email])

    def test_a_re_emitted_event_does_not_duplicate_the_row(self):
        from leave.cancellations.events import CancellationEvent

        app = self.make_approved()
        request = self.request_cancellation(app)
        event = CancellationEvent(
            kind="cancellation.requested",
            application_id=str(app.pk),
            request_id=str(request.pk),
            outcome=CancellationRequest.Status.PENDING,
            recipient_user_ids=[self.employee.pk],
        )

        queue_cancellation_email(event)
        queue_cancellation_email(event)

        self.assertEqual(
            NotificationOutbox.objects.filter(
                cancellation=request, kind=KIND_CANCELLATION_REQUESTED
            ).count(),
            1,
        )

    def test_an_unknown_event_kind_queues_nothing(self):
        from leave.cancellations.events import CancellationEvent

        app = self.make_approved()
        request = self.request_cancellation(app)
        before = [row.kind for row in self.rows(request)]

        with self.assertLogs("notifications.cancellations", level="WARNING"):
            queue_cancellation_email(
                CancellationEvent(
                    kind="cancellation.teleported",
                    application_id=str(app.pk),
                    request_id=str(request.pk),
                    outcome="pending",
                )
            )

        self.assertEqual([row.kind for row in self.rows(request)], before)
