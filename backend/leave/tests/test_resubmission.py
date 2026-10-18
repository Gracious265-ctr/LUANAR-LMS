"""Resubmission service + endpoint tests (Unit 21, §3.7 "New
``leave/tests/test_resubmission.py``").

Contract under test (D9):
- 404 ``RESUBMISSION_NOT_FOUND`` — missing application, or one not owned by the
  caller (never 403).
- 409 ``NOT_RESUBMITTABLE`` — status is not ``rejected``/``correction_required``.
- 409 ``WORKFLOW_INCONSISTENT`` — returning stage is gone or was not
  rejected/correction-requested.
- 422 ``VALIDATION_FAILED`` — the re-validation (snapshot re-run) fails.
- Happy path: ``submission_cycle + 1``, the returning stage re-opened in place
  (``pending``, ``decision_version + 1``), ``current_stage`` points at it,
  ``current_approver`` = returning stage's configured ``assigned_approver``,
  reference number stable, ``application_resubmitted`` audit row,
  ``leave_application_submitted`` signal, and ``assign_workflow`` is **not**
  re-run (the spine is never rebuilt).

The scenario helpers build state through the real submission/decision services
on the stub provider's 4-role spine, exactly like the Unit 15 tracking tests.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import F
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from leave.models import LeaveApplication
from leave.services.resubmission import (
    NotResubmittableError,
    ResubmissionNotFoundError,
    WorkflowInconsistentError,
    resubmit_application,
)
from leave.services.submission import (
    ApplicationNotFoundError,
    submit_application,
)
from approvals.models import ApplicationStage
from approvals.models import ApprovalDecision
from approvals.services import decide

from .stubs import EARLIEST_ANNUAL_START, StubProviderMixin, make_user

User = get_user_model()

RESUBMIT_URL = "/api/v1/leave-applications/{id}/resubmit/"


class StubFlowBaseTests(StubProviderMixin, TestCase):
    """Employee + 4-role spine + owner client (mirrors tracking tests)."""

    def setUp(self):
        super().setUp()
        self.stub = self.use_stub()
        self.client = APIClient()
        self.owner = make_user(
            "resub.owner@luanar", first_name="Koga", last_name="Employee"
        )
        self.supervisor = make_user(
            "resub.supervisor@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user(
            "resub.hod@luanar",
            role="hod",
            first_name="Hady",
            last_name="Od",
        )
        self.registrar = make_user(
            "resub.registrar@luanar",
            role="registrar",
            first_name="Rej",
            last_name="Registrar",
        )
        self.stub.register_employee(self.owner)
        for role, user in (
            ("supervisor", self.supervisor),
            ("hod", self.hod),
            ("registrar", self.registrar),
        ):
            self.stub.workflow.register_approver(role, user)
        self.client.force_authenticate(user=self.owner)

    def url(self, app_id):
        return RESUBMIT_URL.format(id=app_id)

    def make_submitted(self):
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            reason="Family visit",
        )
        return submit_application(user=self.owner, application_id=app.pk)

    def make_rejected(self):
        app = self.make_submitted()
        decide(
            application_id=app.pk,
            actor=self.supervisor,
            action=ApprovalDecision.Action.REJECT,
            comment="Dates clash with another trip.",
            expected_version=1,
        )
        app.refresh_from_db()
        return app


class ResubmissionServiceTests(StubFlowBaseTests):
    def test_missing_application_raises_not_found(self):
        with self.assertRaises(ResubmissionNotFoundError):
            resubmit_application(user=self.owner, application_id=uuid.uuid4())

    def test_foreign_application_raises_not_found(self):
        other = make_user(
            "resub.other@luanar", first_name="Othe", last_name="R"
        )
        self.stub.register_employee(other)
        app = self.make_rejected()
        raise_exception = False
        try:
            resubmit_application(user=other, application_id=app.pk)
        except ResubmissionNotFoundError:
            raise_exception = True
        self.assertTrue(raise_exception)

    def test_draft_status_is_not_resubmittable(self):
        app = LeaveApplication.objects.create(
            employee=self.owner,
            leave_type_id=1,
            start_date=EARLIEST_ANNUAL_START,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=2),
            reason="Family visit",
        )
        from leave.services.resubmission import NotResubmittableError as _err

        with self.assertRaises(_err):
            resubmit_application(user=self.owner, application_id=app.pk)

    def test_cancelled_status_is_not_resubmittable(self):
        app = self.make_rejected()
        app.status = LeaveApplication.Status.CANCELLED
        app.save(update_fields=["status"])
        with self.assertRaises(NotResubmittableError):
            resubmit_application(user=self.owner, application_id=app.pk)

    def test_revalidation_failure_reraises_422(self):
        from leave.services.resubmission import NotResubmittableError as _nre
        from leave.services.submission import ValidationFailedError
        from unittest import mock

        app = self.make_rejected()
        mock.patch(
            "leave.services.resubmission.run_validation",
            side_effect=lambda **kw: None if False else _FakeResult(),  # noqa: E731
        )
        # The stub provider is permissive; simulate an annual-balance shortage.
        self.stub.set_balance(self.owner.id, "2026-27", 1)
        with self.assertRaises(ValidationFailedError) as ctx:
            resubmit_application(user=self.owner, application_id=app.pk)
        self.assertGreaterEqual(len(ctx.exception.errors), 1)

    def test_resubmission_audit_detail_is_json_safe(self):
        import json

        from audit.models import AuditEntry

        app = self.make_rejected()
        resubmit_application(user=self.owner, application_id=app.pk)

        entry = AuditEntry.objects.get(
            action=AuditEntry.Action.APPLICATION_RESUBMITTED
        )
        json.dumps(entry.detail)
        self.assertEqual(entry.detail["after"]["submission_cycle"], 2)
        self.assertIsInstance(entry.detail["after"]["decision_version"], int)
        self.assertEqual(entry.detail["after"]["decision_version"], 3)

    def test_resubmission_freezes_a_new_revision_with_the_diff(self):
        from leave.models import ApplicationRevision

        app = self.make_rejected()
        cycle_one = ApplicationRevision.objects.get(application=app)

        app.reason = "Family visit (dates corrected)"
        app.save(update_fields=["reason"])
        resubmit_application(user=self.owner, application_id=app.pk)

        self.assertEqual(ApplicationRevision.objects.filter(application=app).count(), 2)
        cycle_two = ApplicationRevision.objects.get(application=app, revision_number=2)
        self.assertEqual(cycle_two.reason, "Family visit (dates corrected)")
        self.assertEqual(cycle_two.changes["before"]["reason"], "Family visit")
        self.assertEqual(
            cycle_two.changes["after"]["reason"], "Family visit (dates corrected)"
        )

        # The cycle-1 row is untouched history, not rewritten by the resubmission.
        cycle_one.refresh_from_db()
        self.assertEqual(cycle_one.reason, "Family visit")
        self.assertIsNone(cycle_one.changes)

    def test_revision_write_failure_rolls_back_resubmission(self):
        from unittest import mock

        from audit.models import AuditEntry
        from leave.models import ApplicationRevision

        app = self.make_rejected()
        with mock.patch(
            "leave.models.ApplicationRevision.objects.create",
            side_effect=RuntimeError("revision store down"),
        ):
            with self.assertRaises(RuntimeError):
                resubmit_application(user=self.owner, application_id=app.pk)

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)
        self.assertEqual(app.submission_cycle, 1)
        self.assertEqual(ApplicationRevision.objects.filter(application=app).count(), 1)
        self.assertFalse(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.APPLICATION_RESUBMITTED
            ).exists()
        )


class _FakeResult:
    valid = False
    errors = ["INSUFFICIENT_BALANCE"]
