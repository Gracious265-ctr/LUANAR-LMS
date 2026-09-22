"""Service-level tests for ``leave.services.submission.submit_application``."""

from datetime import date
from decimal import Decimal
from threading import Thread
from unittest import mock

from django.test import TestCase, TransactionTestCase

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.services.submission import (
    AlreadySubmittedError,
    ApplicationNotFoundError,
    ApplicationNotSubmittableError,
    ValidationFailedError,
    submit_application,
)
from leave.signals import leave_application_submitted

from .stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_user,
)


class SubmissionServiceTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)

    def draft(self, **kwargs):
        defaults = dict(
            employee=self.user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )
        defaults.update(kwargs)
        return LeaveApplication.objects.create(**defaults)

    def test_happy_path_persists_submission_fields(self):
        app = self.draft()
        submitted = submit_application(user=self.user, application_id=app.id)
        app.refresh_from_db()

        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertIsNotNone(app.submitted_at)
        self.assertEqual(app.working_days, 5)
        self.assertEqual(app.calendar_days, 5)
        self.assertEqual(app.financial_year_label, "2026-27")
        self.assertEqual(app.reference_number, "LV-2026-27-000001")
        self.assertEqual(submitted.pk, app.pk)

    def test_reference_is_never_regenerated(self):
        app = self.draft(reference_number="LV-2026-27-000123")
        submit_application(user=self.user, application_id=app.id)
        app.refresh_from_db()
        self.assertEqual(app.reference_number, "LV-2026-27-000123")

    def test_rules_snapshot_is_stored(self):
        app = self.draft()
        submit_application(user=self.user, application_id=app.id)
        app.refresh_from_db()
        self.assertEqual(app.rules_snapshot["validator_version"], "1")
        self.assertEqual(app.rules_snapshot["leave_type"]["code"], "annual")
        self.assertEqual(
            app.rules_snapshot["financial_year"]["label"], "2026-27"
        )
        self.assertEqual(app.rules_snapshot["working_days"], 5)
        self.assertEqual(app.rules_snapshot["available_balance"], "24")

    def test_audit_event_is_written(self):
        app = self.draft()
        submit_application(user=self.user, application_id=app.id)
        event = AuditEntry.objects.get(
            action=AuditEntry.Action.SUBMITTED,
            target_type=AuditEntry.TargetType.APPLICATION,
        )
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.target_summary, "LV-2026-27-000001")
        self.assertEqual(
            event.detail["after"]["reference_number"], "LV-2026-27-000001"
        )
        self.assertEqual(event.detail["after"]["working_days"], 5)

    def test_unowned_application_raises_not_found(self):
        other = make_user(username="other@test.luanar")
        self.stub.register_employee(other)
        app = self.draft(employee=other)
        with self.assertRaises(ApplicationNotFoundError):
            submit_application(user=self.user, application_id=app.id)

    def test_missing_application_raises_not_found(self):
        from uuid import uuid4

        with self.assertRaises(ApplicationNotFoundError):
            submit_application(user=self.user, application_id=uuid4())

    def test_already_submitted_raises_with_reference(self):
        app = self.draft(
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LV-2026-27-000009",
            submitted_at=date.today(),
        )
        with self.assertRaises(AlreadySubmittedError) as ctx:
            submit_application(user=self.user, application_id=app.id)
        self.assertEqual(ctx.exception.reference_number, "LV-2026-27-000009")

    def test_non_draft_status_raises_not_submittable(self):
        app = self.draft(status="pending")
        with self.assertRaises(ApplicationNotSubmittableError):
            submit_application(user=self.user, application_id=app.id)

    def test_validation_failure_raises_with_errors(self):
        self.stub.set_balance(self.user.id, "2026-27", Decimal("0"))
        app = self.draft()
        with self.assertRaises(ValidationFailedError) as ctx:
            submit_application(user=self.user, application_id=app.id)
        codes = {issue.code for issue in ctx.exception.errors}
        self.assertIn("INSUFFICIENT_BALANCE", codes)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)
        self.assertIsNone(app.reference_number)

    def test_failed_submission_writes_no_audit_event(self):
        self.stub.set_balance(self.user.id, "2026-27", Decimal("0"))
        app = self.draft()
        try:
            submit_application(user=self.user, application_id=app.id)
        except ValidationFailedError:
            pass
        self.assertFalse(AuditEntry.objects.exists())


class SubmissionSignalTests(StubProviderMixin, TransactionTestCase):
    """Signal fires only after the outer transaction commits (on_commit)."""

    def test_submission_signal_is_sent_on_commit(self):
        self.stub = self.use_stub()
        user = make_user()
        self.stub.register_employee(user)
        app = LeaveApplication.objects.create(
            employee=user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )

        receiver = mock.Mock()
        leave_application_submitted.connect(receiver)
        self.addCleanup(
            leave_application_submitted.disconnect, receiver
        )

        submit_application(user=user, application_id=app.id)

        receiver.assert_called_once()
        sent = receiver.call_args.kwargs["application"]
        self.assertEqual(sent.id, app.id)
        self.assertEqual(sent.status, LeaveApplication.Status.SUBMITTED)


class ConcurrentSubmissionTests(StubProviderMixin, TransactionTestCase):
    """Two overlapping submissions for one employee: exactly one succeeds."""

    def test_second_overlapping_submission_fails_validation(self):
        self.stub = self.use_stub()
        user = make_user()
        self.stub.register_employee(user)

        app_a = LeaveApplication.objects.create(
            employee=user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="App A",
        )
        app_b = LeaveApplication.objects.create(
            employee=user,
            leave_type_id=1,
            start_date=date(2026, 9, 29),
            end_date=date(2026, 10, 3),
            reason="App B",
        )

        outcomes = {}

        def submit(thread_name, app_id):
            try:
                submit_application(user=user, application_id=app_id)
                outcomes[thread_name] = ("ok", None)
            except Exception as exc:  # noqa: BLE001 - collected for assertions
                outcomes[thread_name] = ("error", type(exc).__name__)

        t1 = Thread(target=submit, args=("a", app_a.id))
        t2 = Thread(target=submit, args=("b", app_b.id))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        states = set(outcome for outcome, _ in outcomes.values())
        self.assertIn("ok", states, outcomes)
        self.assertIn("error", states, outcomes)
        if "error" in states:
            self.assertEqual(
                outcomes["b"][1] if outcomes["b"][0] == "error" else outcomes["a"][1],
                "ValidationFailedError",
            )

        self.assertEqual(
            LeaveApplication.objects.filter(
                status=LeaveApplication.Status.SUBMITTED
            ).count(),
            1,
        )