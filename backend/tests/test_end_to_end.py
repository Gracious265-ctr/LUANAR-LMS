"""Unit 25 — the composed end-to-end system journey (D1, D9, D10).

Each test here walks a real journey through the real services: HR configures
the approval chain, the employee submits, approvers decide, and the ledger,
audit log, revisions, notifications and the two read surfaces are all checked
together. The defects this unit fixed all lived in exactly these seams, so the
tests assert across them rather than per app.
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditEntry
from documents.models import ApprovedLeaveDocument
from documents.tasks import render_approved_document
from leave.cancellations.models import LeaveBalanceTransaction
from leave.cancellations.services import decide_cancellation, submit_cancellation
from leave.models import ApplicationRevision, LeaveApplication
from leave.services.finalise import finalise_approved_application, record_deduction
from leave.services.resubmission import resubmit_application
from leave.services.submission import submit_application
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_user,
)
from notifications.models import NotificationOutbox
from notifications.services import queue_decision_email
from notifications.tasks import deliver_notification
from users.models import EmployeeProfile
from chains.events import (
    APPLICATION_FINALISED,
    DECISION_RECORDED,
    _consumers,
    _reset_consumers_for_tests,
    register_consumer,
)
from approvals.services import decide, reassign_application

User = get_user_model()

#: The real HR-configured chain the journey walks.
CHAIN = ("supervisor", "hod", "registrar", "dvc")

#: The stub rules provider's reference "today" is 2026-09-21, so the earliest
#: annual start (2026-09-28) is the first date satisfying the 5-working-day
#: notice. A three-day span keeps the whole journey inside FY 2026-27.
ANNUAL_START = EARLIEST_ANNUAL_START
ANNUAL_END = ANNUAL_START + timedelta(days=3)

#: A date after submission's reference day but before leave starts, so a
#: cancellation of an approved application is still possible.
CANCEL_DAY = date(2026, 9, 25)


def _restore_consumers(previous):
    """Put the global approval-event bus back as it was found."""
    _reset_consumers_for_tests()
    _consumers.extend(previous)


class EndToEndBase(StubProviderMixin, TestCase):
    """Shared spine: real HR workflow config, real roles, real event bus."""

    def setUp(self):
        self.stub = self.use_stub()

        # Use Unit 21's real HR-configured provider rather than the stub chain,
        # so "HR configured the chain" is genuinely part of the journey.
        patcher = mock.patch(
            "chains.providers.get_workflow_provider",
            return_value=DatabaseWorkflowProvider(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.events = self.capture_events()
        self.client = APIClient()

        self.hr = make_user("hr@luanar", role=User.Role.HR, first_name="Hema")
        self.employee = make_user(
            "employee@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Ken",
            last_name="Employee",
        )
        self.supervisor = make_user(
            "supervisor@luanar",
            role="supervisor",
            first_name="Sana",
            last_name="Supervisor",
        )
        self.hod = make_user("hod@luanar", role="hod", first_name="Hady")
        self.registrar = make_user(
            "registrar@luanar", role="registrar", first_name="Rej"
        )
        self.dvc = make_user("dvc@luanar", role="dvc", first_name="Din")
        # Dean is an approver role that is *not* in the administration chain, so
        # it can stand in as a delegate or a reassignment target without
        # perturbing the role spine.
        self.dean = make_user("dean@luanar", role="dean", first_name="Dena")

        self.stub.register_employee(self.employee)
        # The approvers need employee records; the team they belong to is the
        # one HR configures next, so their profiles are placed on it afterwards.
        # Their category matches the administration team they sit on, the same
        # way a real placement must.
        for approver in (self.supervisor, self.hod, self.registrar, self.dvc):
            EmployeeProfile.objects.update_or_create(
                user=approver,
                defaults={"category": EmployeeProfile.Category.ADMINISTRATION},
            )
        self.employee_profile = EmployeeProfile.objects.create(
            user=self.employee,
            designation="Junior Officer",
            grade="B",
            category=EmployeeProfile.Category.ADMINISTRATION,
        )
        self.chain_approvers = (self.supervisor, self.hod, self.registrar, self.dvc)
        self.chain_roles = dict(zip(CHAIN, self.chain_approvers, strict=True))
        self.team = self.hr_creates_team(CHAIN, self.chain_roles)
        self.chain = self.team["workflows"][0]
        self.team_id = self.team["id"]
        self.workflow_id = self.chain["id"]
        # The chain's approvers are institution-wide, so they are exempt from
        # "an approver must be a member of the team" and resolve straight off
        # their section appointment. They are deliberately *not* placed on the
        # roster: a wide approver staffs steps from the Approvers tab and is
        # refused as a normal member.
        self.place_employee_on_team()

    def capture_events(self):
        """Register an event-capturing consumer, restoring the real bus after.

        django-q2's ``async_task`` is stubbed so the journey never writes to the
        ORM broker; :meth:`deliver_pending` then runs the delivery task for real,
        which is how the journeys below read ``mail.outbox``.
        """
        events = []
        previous = list(_consumers)
        _reset_consumers_for_tests()
        self.async_task = mock.patch("django_q.tasks.async_task").start()
        self.addCleanup(mock.patch.stopall)
        # Keep Unit 22's real email consumer on the bus; only add observation.
        register_consumer(queue_decision_email)
        register_consumer(events.append)
        self.addCleanup(_restore_consumers, previous)
        return events

    def deliver_pending(self):
        """Run the queued delivery for every pending outbox row."""
        for row in NotificationOutbox.objects.filter(state="pending"):
            deliver_notification(row.pk)

    def hr_creates_team(self, roles, approvers):
        """HR creates the team and hands it to a manager, who builds the chain.

        This is the whole configuration sequence as the product now asks for it:
        HR creates the team alone and names its manager — which is the moment it
        is in force — and the manager builds the chain it will route through.
        Each step names one approver, and the team they belong to is what scopes
        them.

        Going through the real endpoints keeps the journey honest: a team the API
        refuses to create fails this test rather than being papered over in a
        fixture.
        """
        self.client.force_authenticate(user=self.hr)
        response = self.client.post(
            "/api/v1/teams/",
            {
                "name": "Administration team",
                "description": "Administration approval chain",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "active")
        team_id = response.data["id"]

        manager = self.designate_manager(team_id)
        self.client.force_authenticate(user=manager)
        chain = self.client.post(
            "/api/v1/workflows/",
            {
                "team": team_id,
                "name": "Administration chain",
                "sections": [
                    {
                        "name": role.title(),
                        "approver_role": role,
                        "approver": approvers[role].id,
                    }
                    for role in roles
                ],
            },
            format="json",
        )
        self.assertEqual(chain.status_code, 201, chain.data)
        self.manager = manager

        self.client.force_authenticate(user=self.hr)
        team = self.client.get(f"/api/v1/teams/{team_id}/")
        self.assertEqual(team.status_code, 200, team.data)
        return team.data

    def designate_manager(self, team_id):
        """Name ``team_id``'s manager as HR and return them.

        The manager role is a team-scoped one created here rather than a shipped
        role, because every shipped role this journey uses is institution-wide
        and an institution-wide role cannot be a team's manager.
        """
        from organisation.models import ApproverRole
        from teams.models import Team
        from organisation.services import create_team_role_assignment

        team = Team.objects.get(pk=team_id)
        manager_role, _ = ApproverRole.objects.get_or_create(
            code="team_manager",
            defaults={
                "label": "Team Manager",
                "description": "The team's designated manager.",
                "history_scope": ApproverRole.HistoryScope.SAME_TEAM,
                "handles_cancellation": False,
                "is_institution_wide": False,
            },
        )
        manager = make_user(
            "manager@luanar",
            role=User.Role.EMPLOYEE,
            first_name="Mona",
            last_name="Manager",
        )
        EmployeeProfile.objects.update_or_create(
            user=manager,
            defaults={"category": EmployeeProfile.Category.ADMINISTRATION},
        )
        create_team_role_assignment(
            team=team,
            role=manager_role,
            user=manager,
            actor=self.hr,
            is_team_manager=True,
        )
        return manager

    def place_employee_on_team(self):
        """Put the applicant on the team and enrol them in its chain.

        Being on a team is not enough to route: an employee follows the chain
        they are a normal member of, so the manager — who owns the roster after
        HR hands the team over — adds them to the workflow.
        """
        self.client.force_authenticate(user=self.hr)
        response = self.client.patch(
            f"/api/v1/employees/{self.employee_profile.id}/",
            {"team": self.team_id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(user=self.manager)
        enrolled = self.client.post(
            f"/api/v1/workflows/{self.workflow_id}/members/",
            {"user": self.employee.pk},
            format="json",
        )
        self.assertEqual(enrolled.status_code, 201, enrolled.data)
        self.client.force_authenticate(user=self.hr)
        self.employee.refresh_from_db()
        return self.employee.employee_profile

    # --- journey steps ---------------------------------------------------

    def submit(self, reason="Family visit", start=ANNUAL_START, end=ANNUAL_END):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            leave_type_id=1,
            start_date=start,
            end_date=end,
            reason=reason,
        )
        with self.captureOnCommitCallbacks(execute=True):
            return submit_application(user=self.employee, application_id=app.pk)

    def decide(self, app, actor, action, **kwargs):
        """One decision, running the on-commit bus (events, emails) for real.

        ``expected_version`` defaults to the live stage version: Unit 17 reuses
        the stage chain across resubmission cycles, so after a rejection and
        resubmission the first approver's stage is no longer at version 1.
        """
        app.refresh_from_db()
        if "expected_version" not in kwargs and app.current_stage_id is not None:
            kwargs["expected_version"] = ApplicationStage.objects.values_list(
                "decision_version", flat=True
            ).get(pk=app.current_stage_id)
        with self.captureOnCommitCallbacks(execute=True):
            result = decide(
                application_id=app.pk,
                actor=actor,
                action=action,
                **kwargs,
            )
        app.refresh_from_db()
        return result

    def approve_whole_chain(self, app, approvers=None):
        for approver in approvers or self.chain_approvers:
            self.decide(app, approver, ApprovalDecision.Action.APPROVE)
        return app

    # --- assertions ------------------------------------------------------

    def deductions(self, app):
        return LeaveBalanceTransaction.objects.filter(
            application=app, type=LeaveBalanceTransaction.Type.DEDUCTION
        )

    def restorations(self, app):
        return LeaveBalanceTransaction.objects.filter(
            application=app, type=LeaveBalanceTransaction.Type.RESTORATION
        )


class FullApprovalJourneyTests(EndToEndBase):
    """D1 — the happy path, asserted across every app at once."""

    def test_full_journey_from_hr_config_to_hr_finalized_record(self):
        app = self.submit()
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertEqual(app.submission_cycle, 1)
        self.assertEqual(
            [s.role for s in app.stages.order_by("stage_order")], list(CHAIN)
        )
        self.assertEqual(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=str(app.pk),
            ).count(),
            1,
            "submission is audited",
        )

        self.approve_whole_chain(app)

        # The decision service, the ledger and the event bus agree.
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(ApprovalDecision.objects.filter(application=app).count(), 4)
        deduction = self.deductions(app)
        self.assertEqual(deduction.count(), 1, "exactly one deduction")
        entry = deduction.get()
        self.assertEqual(entry.employee_id, self.employee.id)
        self.assertEqual(entry.leave_type, app.leave_type_id)
        self.assertEqual(entry.days, app.working_days)
        self.assertEqual(entry.financial_year, app.financial_year_label)
        self.assertEqual(
            [e.kind for e in self.events],
            [DECISION_RECORDED] * 3 + [APPLICATION_FINALISED],
        )

        # The employee's frozen revision for cycle 1 exists (Unit 24).
        revision = ApplicationRevision.objects.get(
            application=app, revision_number=1
        )
        self.assertEqual(revision.leave_type_id, app.leave_type_id)
        self.assertEqual(revision.working_days, app.working_days)
        self.assertEqual(revision.start_date, app.start_date)
        self.assertIsNone(revision.changes, "the first revision has no predecessor")

        # The employee is told the outcome.
        self.deliver_pending()
        self.assertTrue(
            any(app.reference_number in message.subject for message in mail.outbox)
        )

        # The employee sees their approved application (HTTP contract).
        self.client.force_authenticate(user=self.employee)
        mine = self.client.get("/api/v1/leave-applications/")
        self.assertEqual(mine.status_code, 200)
        row = next(r for r in mine.data["results"] if r["id"] == str(app.pk))
        self.assertEqual(row["status"], LeaveApplication.Status.APPROVED)

        # HR sees the finalized record (the D6 fix).
        self.client.force_authenticate(user=self.hr)
        finalized = self.client.get("/api/v1/finalized-leave/")
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.data["count"], 1)
        self.assertEqual(
            finalized.data["results"][0]["reference_number"], app.reference_number
        )
        detail = self.client.get(f"/api/v1/finalized-leave/{app.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["reference_number"], app.reference_number)

    def test_approval_never_double_deducts_across_repeated_finalization(self):
        """D3 — the partial unique constraint makes the ledger write once-only."""
        app = self.submit()
        self.approve_whole_chain(app)
        # A second finalization attempt (e.g. a retried job) must not add a row.
        record_deduction(app)
        record_deduction(app)
        self.assertEqual(self.deductions(app).count(), 1)

    def test_ledger_constraint_rejects_a_second_deduction_row(self):
        app = self.submit()
        self.approve_whole_chain(app)
        first = self.deductions(app).get()
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LeaveBalanceTransaction.objects.create(
                    employee=self.employee,
                    financial_year=first.financial_year,
                    leave_type=first.leave_type,
                    application=app,
                    type=LeaveBalanceTransaction.Type.DEDUCTION,
                    days=first.days,
                )

    def test_one_outbox_email_per_decision(self):
        app = self.submit()
        self.approve_whole_chain(app)
        self.assertEqual(
            NotificationOutbox.objects.count(),
            4,
            "one decision email per approval, no duplicates",
        )


class RejectionJourneyTests(EndToEndBase):
    def test_rejection_stops_the_chain_writes_no_deduction_and_emails_the_owner(self):
        app = self.submit()
        result = self.decide(
            app,
            self.supervisor,
            ApprovalDecision.Action.REJECT,
            comment="Insufficient documentation.",
        )
        self.assertEqual(result.status, LeaveApplication.Status.REJECTED)
        app.refresh_from_db()
        self.assertEqual(self.deductions(app).count(), 0)
        self.assertEqual([e.kind for e in self.events], [DECISION_RECORDED])
        # Later stages never become actionable.
        pending = ApplicationStage.objects.filter(
            application=app, status=ApplicationStage.Status.PENDING
        )
        self.assertEqual(pending.count(), 0)
        self.deliver_pending()
        self.assertTrue(
            any(app.reference_number in message.subject for message in mail.outbox)
        )


class RejectionAndResubmissionJourneyTests(EndToEndBase):
    def test_rejection_then_resubmission_freezes_a_new_cycle_and_deducts_once(self):
        app = self.submit()
        self.decide(
            app,
            self.supervisor,
            ApprovalDecision.Action.REJECT,
            comment="Please attach the medical note.",
        )
        self.assertEqual(app.status, LeaveApplication.Status.REJECTED)

        # Cycle 1's revision is frozen; the employee may now edit (D7).
        self.client.force_authenticate(user=self.employee)
        edited = self.client.patch(
            f"/api/v1/leave-applications/{app.pk}/",
            {"reason": "Family visit (corrected dates confirmed)"},
            format="json",
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        cycle1 = ApplicationRevision.objects.get(
            application=app, revision_number=1
        )
        self.assertEqual(cycle1.reason, "Family visit")

        app = resubmit_application(user=self.employee, application_id=app.pk)
        self.assertEqual(app.submission_cycle, 2)
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertEqual(
            ApplicationRevision.objects.filter(application=app).count(), 2
        )
        cycle2 = ApplicationRevision.objects.get(
            application=app, revision_number=2
        )
        self.assertEqual(cycle2.reason, "Family visit (corrected dates confirmed)")
        self.assertEqual(
            cycle2.changes,
            {
                "before": {"reason": "Family visit"},
                "after": {"reason": "Family visit (corrected dates confirmed)"},
            },
        )
        cycle1.refresh_from_db()
        self.assertEqual(cycle1.reason, "Family visit", "cycle 1 stays untouched")

        self.approve_whole_chain(app)
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.deductions(app).count(), 1, "deducted once, after resubmit")

    def test_a_submitted_application_cannot_be_edited(self):
        """D7 — only draft and rejected are editable."""
        app = self.submit()
        self.client.force_authenticate(user=self.employee)
        response = self.client.patch(
            f"/api/v1/leave-applications/{app.pk}/",
            {"reason": "Sneaky edit"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        app.refresh_from_db()
        self.assertEqual(app.reason, "Family visit")


class CancellationJourneyTests(EndToEndBase):
    def test_cancelling_an_approved_application_restores_the_deduction(self):
        app = self.submit()
        self.approve_whole_chain(app)
        deduction = self.deductions(app).get()

        request = submit_cancellation(
            user=self.employee,
            application_id=app.pk,
            reason="Plans changed.",
            confirm=True,
            expected_action="request",
            today=CANCEL_DAY,
        )
        # The cancellation walks the supervisor/hod snapshot stages.
        stage_version = 1
        for approver in (self.supervisor, self.hod):
            with self.captureOnCommitCallbacks(execute=True):
                request = decide_cancellation(
                    user=approver,
                    request_id=request.pk,
                    decision="approve",
                    stage_version=stage_version,
                    today=CANCEL_DAY,
                )
            stage_version += 1
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.CANCELLED)
        restoration = self.restorations(app).get()
        self.assertEqual(restoration.days, deduction.days)
        self.assertEqual(restoration.financial_year, deduction.financial_year)
        self.assertFalse(restoration.carry_forward_eligible)
        # Net zero: the deduction is offset by exactly one restoration.
        net = sum(
            t.days * (-1 if t.type == LeaveBalanceTransaction.Type.DEDUCTION else 1)
            for t in LeaveBalanceTransaction.objects.filter(application=app)
        )
        self.assertEqual(net, 0)


class DelegationJourneyTests(EndToEndBase):
    def test_an_approved_delegate_can_decide_the_approvers_stage(self):
        app = self.submit()
        # The window is expressed relative to today rather than as fixed dates,
        # because a delegation only covers an approver while it is in effect
        # (``workflows.services._active_delegation_for_id`` filters on the local
        # date). Hard-coded dates here made this test start failing the day the
        # window passed, with a "not_current_stage" error that pointed at the
        # approval chain rather than at an expired delegation.
        today = timezone.localdate()
        delegation = Delegation.objects.create(
            approver=self.supervisor,
            delegate=self.dean,
            starts_on=today - timedelta(days=1),
            ends_on=today + timedelta(days=9),
            requested_by=self.supervisor,
            status=Delegation.Status.APPROVED,
        )
        self.assertTrue(delegation.pk)
        # The delegate, not the supervisor, acts on stage 1.
        self.decide(app, self.dean, ApprovalDecision.Action.APPROVE)
        self.assertEqual(
            ApplicationStage.objects.get(
                application=app, submission_cycle=1, stage_order=1
            ).status,
            ApplicationStage.Status.APPROVED,
        )
        self.approve_whole_chain(app, self.chain_approvers[1:])
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.deductions(app).count(), 1)


class ReassignmentJourneyTests(EndToEndBase):
    def test_a_reassigned_stage_can_be_decided_by_its_new_approver(self):
        app = self.submit()
        reassignment = reassign_application(
            application=app,
            to_approver=self.dean,
            actor=self.supervisor,
            reason="Supervisor on study leave.",
        )
        self.assertIsInstance(reassignment, Reassignment)
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.dean.id)
        # The new approver decides stage 1.
        self.decide(app, self.dean, ApprovalDecision.Action.APPROVE)
        self.approve_whole_chain(app, self.chain_approvers[1:])
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.deductions(app).count(), 1)
        self.assertEqual(Reassignment.objects.filter(application=app).count(), 1)


class ApprovedDocumentJourneyTests(EndToEndBase):
    """Unit 23b — the document half of the approval, asserted end to end.

    Runs the real decision service, the real finalisation orchestrator and the
    real render task; only the Supabase client and the Q2 broker are stubbed,
    because neither is what this journey is about.
    """

    def approve_and_render(self, app):
        """Approve the whole chain, then run the render task as a worker would."""
        self.approve_whole_chain(app)
        app.refresh_from_db()
        document = ApprovedLeaveDocument.objects.get(application=app)
        with mock.patch(
            "leave.services.storage.get_supabase_client", return_value=self._fake_client()
        ):
            render_approved_document(document.pk)
        document.refresh_from_db()
        return document

    def _fake_client(self):
        class _Bucket:
            def upload(self, path, data, opts):
                self.data = data

            def create_signed_url(self, path, expiry):
                return {"signedURL": f"https://signed/{path}"}

        class _Client:
            def __init__(self):
                self.storage = self
                self.bucket = _Bucket()

            def from_(self, bucket):
                return self.bucket

        return _Client()

    def test_approval_creates_a_pending_document_with_the_approval_stamp(self):
        app = self.submit()
        self.approve_whole_chain(app)
        app.refresh_from_db()

        self.assertIsNotNone(app.approved_on, "the final approval is stamped")
        document = ApprovedLeaveDocument.objects.get(application=app)
        self.assertEqual(document.status, ApprovedLeaveDocument.Status.PENDING)
        self.assertEqual(document.application_id, app.pk)

    def test_the_document_reaches_ready_and_the_owner_can_download_it(self):
        app = self.submit()
        document = self.approve_and_render(app)

        self.assertEqual(document.status, ApprovedLeaveDocument.Status.READY)
        self.assertTrue(document.is_available)
        self.assertEqual(document.file_name, "approved-leave.pdf")
        self.assertEqual(document.content_type, "application/pdf")
        self.assertTrue(document.file_path.startswith(f"approved/{app.pk}/"))

        self.client.force_authenticate(user=self.employee)
        with mock.patch(
            "leave.services.storage.signed_document_url",
            return_value="https://signed/fresh",
        ):
            response = self.client.get(
                f"/api/v1/approved-leave-documents/by-application/{app.pk}/"
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["available"])
        self.assertEqual(response.data["download_url"], "https://signed/fresh")

    def test_the_render_is_audited_as_a_system_action(self):
        app = self.submit()
        self.approve_and_render(app)
        entry = AuditEntry.objects.get(
            action=AuditEntry.Action.DOCUMENT_GENERATED,
            target_id=str(app.pk),
        )
        self.assertIsNone(entry.actor, "the worker, not a person, generated it")
        self.assertEqual(entry.target_type, AuditEntry.TargetType.APPLICATION)

    def test_hr_reads_the_document_through_the_audit_route(self):
        app = self.submit()
        document = self.approve_and_render(app)
        self.client.force_authenticate(user=self.hr)
        with mock.patch(
            "leave.services.storage.signed_document_url",
            return_value="https://signed/hr",
        ):
            response = self.client.get(
                f"/api/v1/hr/approved-leave-documents/by-application/{app.pk}/"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["download_url"], "https://signed/hr")

    def test_an_unrelated_employee_cannot_reach_the_document(self):
        from users.models import User

        app = self.submit()
        document = self.approve_and_render(app)
        stranger = User.objects.create_user(
            username="stranger@luanar",
            email="stranger@luanar",
            password="pw",
            role=User.Role.EMPLOYEE,
        )
        self.client.force_authenticate(user=stranger)
        response = self.client.get(
            f"/api/v1/approved-leave-documents/by-application/{app.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_a_render_failure_leaves_the_approval_and_deduction_intact(self):
        app = self.submit()
        self.approve_whole_chain(app)
        app.refresh_from_db()
        document = ApprovedLeaveDocument.objects.get(application=app)
        with mock.patch(
            "documents.tasks.render_approved_document_pdf",
            side_effect=RuntimeError("renderer offline"),
        ):
            render_approved_document(document.pk)

        document.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(document.status, ApprovedLeaveDocument.Status.FAILED)
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.deductions(app).count(), 1)
        self.assertTrue(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.DOCUMENT_FAILED, target_id=str(app.pk)
            ).exists()
        )

    def test_repeated_finalization_reuses_the_same_document(self):
        app = self.submit()
        self.approve_whole_chain(app)
        app.refresh_from_db()

        finalise_approved_application(app)
        finalise_approved_application(app)
        self.assertEqual(ApprovedLeaveDocument.objects.filter(application=app).count(), 1)
        self.assertEqual(self.deductions(app).count(), 1)
