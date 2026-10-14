"""Service-level tests for ``leave.services.submission.submit_application``."""

from datetime import date
from decimal import Decimal
from threading import Thread
from unittest import mock

from django.test import TestCase, TransactionTestCase

from audit.models import AuditEntry
from leave.models import (
    ApplicationRevision,
    ApplicationRevisionLockedError,
    LeaveApplication,
    SupportingDocument,
)
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
    make_approver_chain,
    make_user,
    register_chain_approvers,
)


class SubmissionServiceTests(StubProviderMixin, TestCase):
    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)
<<<<<<< HEAD
        make_approver_chain()
=======
        register_chain_approvers(self.stub)
>>>>>>> feature/plans-teams

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

        self.assertEqual(app.status, LeaveApplication.Status.PENDING)
        self.assertIsNotNone(app.submitted_at)
        self.assertEqual(app.working_days, 5)
        self.assertEqual(app.calendar_days, 5)
        self.assertEqual(app.financial_year_label, "2026-27")
        self.assertEqual(app.reference_number, "LV-2026-27-000001")
        self.assertEqual(submitted.pk, app.pk)

    def test_submission_routes_through_workflow(self):
        app = self.draft()
        submit_application(user=self.user, application_id=app.id)
        app.refresh_from_db()

        stage_rows = list(app.stages.all())
        self.assertEqual(len(stage_rows), 4)
        self.assertEqual(stage_rows[0].status, "pending")
        self.assertEqual(stage_rows[0].is_final, False)
        self.assertEqual(stage_rows[-1].status, "waiting")
        self.assertEqual(stage_rows[-1].is_final, True)
        self.assertEqual(app.current_stage_id, stage_rows[0].id)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="leave_application.workflow_assigned"
            ).exists()
        )

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

    def test_pending_application_raises_already_submitted_with_reference(self):
        app = self.draft(
            status=LeaveApplication.Status.PENDING,
            reference_number="LV-2026-27-000044",
        )
        with self.assertRaises(AlreadySubmittedError) as ctx:
            submit_application(user=self.user, application_id=app.id)
        self.assertEqual(ctx.exception.reference_number, "LV-2026-27-000044")

    def test_non_draft_status_raises_not_submittable(self):
        app = self.draft(status=LeaveApplication.Status.REJECTED)
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

    def test_submission_freezes_cycle_one_revision(self):
        app = self.draft()
        submit_application(user=self.user, application_id=app.id)
        app.refresh_from_db()

        revision = ApplicationRevision.objects.get(application=app)
        self.assertEqual(revision.revision_number, 1)
        self.assertEqual(revision.created_by, self.user)
        self.assertEqual(revision.start_date, app.start_date)
        self.assertEqual(revision.end_date, app.end_date)
        self.assertEqual(revision.working_days, 5)
        self.assertEqual(revision.reason, "Annual leave")
        self.assertEqual(revision.leave_type_id, app.leave_type_id)
        self.assertEqual(
            revision.leave_type_name, app.rules_snapshot["leave_type"]["name"]
        )
        self.assertIsNone(revision.changes)
        self.assertEqual(revision.documents, [])

    def test_failed_submission_writes_no_revision(self):
        self.stub.set_balance(self.user.id, "2026-27", Decimal("0"))
        app = self.draft()
        with self.assertRaises(ValidationFailedError):
            submit_application(user=self.user, application_id=app.id)
        self.assertFalse(ApplicationRevision.objects.exists())

    def test_revision_write_failure_rolls_back_submission(self):
        app = self.draft()
        with mock.patch(
            "leave.models.ApplicationRevision.objects.create",
            side_effect=RuntimeError("revision store down"),
        ):
            with self.assertRaises(RuntimeError):
                submit_application(user=self.user, application_id=app.id)

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)
        self.assertIsNone(app.reference_number)
        self.assertIsNone(app.submitted_at)
        self.assertFalse(ApplicationRevision.objects.exists())
        self.assertFalse(AuditEntry.objects.exists())

    def test_revision_freezes_only_active_documents(self):
        app = self.draft()
        active = SupportingDocument.objects.create(
            application=app,
            file_path="active.pdf",
            file_url="https://example.test/active.pdf",
            file_name="active.pdf",
            file_size=100,
            content_type="application/pdf",
        )
        retired = SupportingDocument.objects.create(
            application=app,
            file_path="old.pdf",
            file_url="https://example.test/old.pdf",
            file_name="old.pdf",
            file_size=200,
            content_type="application/pdf",
        )
        retired.retire(self.user, SupportingDocument.RetireReason.REMOVED)

        submit_application(user=self.user, application_id=app.id)

        revision = ApplicationRevision.objects.get(application=app)
        self.assertEqual(
            [document["file_name"] for document in revision.documents],
            ["active.pdf"],
        )
        self.assertEqual(revision.documents[0]["id"], str(active.id))
        self.assertEqual(revision.documents[0]["file_size"], 100)


class ApplicationRevisionIntegrityTests(StubProviderMixin, TestCase):
    """A frozen cycle row is write-only history like ``ApprovalDecision``."""

    def setUp(self):
        self.stub = self.use_stub()
        self.user = make_user()
        self.stub.register_employee(self.user)
        register_chain_approvers(self.stub)
        app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=date(2026, 10, 2),
            reason="Annual leave",
        )
        submit_application(user=self.user, application_id=app.id)
        self.revision = ApplicationRevision.objects.get(application=app)

    def test_instance_update_is_rejected(self):
        self.revision.reason = "rewritten"
        with self.assertRaises(ApplicationRevisionLockedError):
            self.revision.save()
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.reason, "Annual leave")

    def test_instance_delete_is_rejected(self):
        with self.assertRaises(ApplicationRevisionLockedError):
            self.revision.delete()
        self.assertTrue(ApplicationRevision.objects.filter(pk=self.revision.pk).exists())

    def test_queryset_update_is_rejected(self):
        with self.assertRaises(ApplicationRevisionLockedError):
            ApplicationRevision.objects.filter(pk=self.revision.pk).update(
                reason="rewritten"
            )
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.reason, "Annual leave")

    def test_queryset_delete_is_rejected(self):
        with self.assertRaises(ApplicationRevisionLockedError):
            ApplicationRevision.objects.filter(pk=self.revision.pk).delete()
        self.assertTrue(ApplicationRevision.objects.filter(pk=self.revision.pk).exists())


class SubmissionSignalTests(StubProviderMixin, TransactionTestCase):
    """Signal fires only after the outer transaction commits (on_commit)."""

    def test_submission_signal_is_sent_on_commit(self):
        self.stub = self.use_stub()
        user = make_user()
        self.stub.register_employee(user)
<<<<<<< HEAD
        make_approver_chain()
=======
        register_chain_approvers(self.stub)
>>>>>>> feature/plans-teams
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
        self.assertEqual(sent.status, LeaveApplication.Status.PENDING)


class ConcurrentSubmissionTests(StubProviderMixin, TransactionTestCase):
    """Two overlapping submissions for one employee: exactly one succeeds."""

    def test_second_overlapping_submission_fails_validation(self):
        self.stub = self.use_stub()
        user = make_user()
        self.stub.register_employee(user)
<<<<<<< HEAD
        make_approver_chain()
=======
        register_chain_approvers(self.stub)
>>>>>>> feature/plans-teams

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
                status=LeaveApplication.Status.PENDING
            ).count(),
            1,
        )