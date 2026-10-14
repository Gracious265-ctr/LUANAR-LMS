"""The self-approval business rule: an applicant is never an approver of record.

Under sections, the rule has three shapes, and these are the cases this module
pins:

* **a shared section still routes** — the applicant sits on a section with a
  colleague, the applicant is removed from its eligibility snapshot, and the
  colleague decides it. Nothing is skipped and the chain still starts at
  section one;
* **a section staffed only by the applicant is skipped** (Unit 30) — there is
  nobody left to act, so the stage is materialised as ``SKIPPED`` with the reason
  recorded, every stage below it is skipped too, and the application opens at the
  first stage above;
* **when the applicant holds the last stage, the application goes to HR** — there
  is no higher stage to open at, so a final HR stage is appended rather than the
  application being refused or finalised by nobody.

A section with *nobody* in it is a different problem and is still refused
(invariant 12.7): there is no applicant to blame and nowhere to send it. That is
:class:`UnstaffedStageIsStillRefusedTests`.

The same check also has to hold on rows that predate sections, where the chain
was built by skipping forward; those are covered by
:class:`AdvanceTimeBlockIsDefenseInDepth`.

The shared predicate itself lives in :mod:`workflows.policies`; the cancellation
guard that reuses it is covered in ``leave.tests.test_cancellations``.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditEntry
from leave.models import LeaveApplication
from leave.services.submission import (
    ValidationFailedError,
    submit_application,
)
from leave.tests.stubs import (
    EARLIEST_ANNUAL_START,
    StubProviderMixin,
    make_user,
)
from users.models import EmployeeProfile

from .testing import team_for
from .models import (
    ApplicationStage,
    ApprovalDecision,
    Delegation,
    Reassignment,
)
from .policies import get_decision_authority, is_self_application
from .services import (
    ApprovalNotAllowedError,
    ReassignmentError,
    SelfApprovalBlockedError,
    decide,
    reassign_application,
)

User = get_user_model()

ANNUAL = {
    "leave_type_id": 1,
    "start_date": EARLIEST_ANNUAL_START,
    "reason": "Family visit",
}


class SelfApprovalBase(StubProviderMixin, TestCase):
    """The applicant also holds a real approver role, so a section can be them."""

    def setUp(self):
        self.stub = self.use_stub()
        self.employee = make_user(
            "emp@selfapproval",
            role="hod",
            first_name="Nia",
            last_name="Applicant",
        )
        self.supervisor = make_user(
            "sup@selfapproval",
            role="supervisor",
            first_name="Sam",
            last_name="Supervisor",
        )
        self.other_hod = make_user(
            "hod2@selfapproval",
            role="hod",
            first_name="Hana",
            last_name="OtherHod",
        )
        self.registrar = make_user(
            "reg@selfapproval",
            role="registrar",
            first_name="Rio",
            last_name="Registrar",
        )
        self.dvc = make_user(
            "dvc@selfapproval",
            role="dvc",
            first_name="Dev",
            last_name="Vc",
        )
        self.hr = make_user(
            "hr@selfapproval", role=User.Role.HR, first_name="Har", last_name="Hr"
        )
        self.stub.register_employee(self.employee)
        EmployeeProfile.objects.create(
            user=self.employee,
            designation="Officer",
            team=team_for("Administration"),
            grade="B",
        )

    def staff_role(self, role, *users):
        for user in users:
            self.stub.workflow.register_approver(role, user)

    def submit(self):
        app = LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )
        return submit_application(user=self.employee, application_id=app.pk)

    def stage_at(self, app, order):
        return app.stages.get(stage_order=order)

    def approve(self, app, actor, version=1):
        return decide(
            application_id=app.pk,
            actor=actor,
            action=ApprovalDecision.Action.APPROVE,
            expected_version=version,
        )

    def draft(self):
        return LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )

    def assertRefused(self, *sections, message_parts=()):
        app = self.draft()
        with self.assertRaises(ValidationFailedError) as caught:
            submit_application(user=self.employee, application_id=app.pk)
        errors = caught.exception.errors
        self.assertTrue(errors)
        for error in errors:
            self.assertEqual(error.code, "workflow_unavailable")
        app.refresh_from_db()
        # A refused submission leaves nothing behind: a half-built chain would
        # be worse than none, because it would look routable.
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)
        self.assertEqual(app.stages.count(), 0)
        message = " ".join(error.message for error in errors)
        for part in message_parts:
            self.assertIn(part, message)
        for section in sections:
            self.assertIn(f'"{section}" approval section', message)
        return message


class SharedSectionStillRoutesTests(SelfApprovalBase):
    """A section the applicant shares with a colleague is decided by them.

    ``supervisor -> HOD -> Registrar`` with the applicant as one of two HODs. The
    chain starts at section one, the HOD section is live, and the other HOD is
    the only person in its eligibility set.
    """

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee, self.other_hod)
        self.staff_role("registrar", self.registrar)

    def test_the_chain_starts_at_the_first_section(self):
        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.PENDING
        )
        self.assertEqual(
            [s.status for s in app.stages.order_by("stage_order")],
            [
                ApplicationStage.Status.PENDING,
                ApplicationStage.Status.WAITING,
                ApplicationStage.Status.WAITING,
            ],
        )
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 1)
        self.assertEqual(app.current_approver_id, None)

    def test_nothing_is_ever_skipped(self):
        app = self.submit()

        self.assertEqual(app.stages.filter(status="skipped").count(), 0)
        self.assertFalse(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.STAGE_SKIPPED
            ).exists()
        )

    def test_the_applicant_is_removed_from_their_own_sections_eligibility(self):
        app = self.submit()

        for order in (1, 2, 3):
            self.assertNotIn(
                self.employee.id,
                self.stage_at(app, order).eligible_approver_ids(),
                f"the applicant is in section {order}'s eligibility",
            )

    def test_their_colleague_decides_the_shared_section(self):
        app = self.submit()
        hod_stage = self.stage_at(app, 2)

        self.assertEqual(hod_stage.eligible_approver_ids(), (self.other_hod.id,))
        self.approve(app, self.supervisor)
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)
        self.approve(app, self.other_hod)
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 3)
        self.assertEqual(
            self.stage_at(app, 2).assigned_approver_id, self.other_hod.id
        )

    def test_the_applicant_is_never_offered_the_section(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        pending = client.get("/api/v1/approvals/?tab=pending").data["results"]
        self.assertNotIn(str(app.pk), [row["id"] for row in pending])
        self.assertFalse(get_decision_authority(self.employee, app).can_decide)
        self.assertEqual(
            get_decision_authority(self.employee, app).reason, "self_application"
        )
        # Nor can they read it: they are not on the path at all.
        self.assertEqual(
            client.get(f"/api/v1/approvals/{app.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_the_reviewer_sees_the_whole_chain_with_no_skips(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.supervisor)

        response = client.get(f"/api/v1/approvals/{app.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stages = {row["order"]: row for row in response.data["workflow"]["stages"]}
        self.assertEqual(
            [stages[order]["status"] for order in (1, 2, 3)],
            ["pending", "waiting", "waiting"],
        )
        self.assertEqual(
            response.data["workflow"]["current_stage"]["next_role_label"],
            "Head of Department",
        )

    def test_tracking_reports_no_skipped_states(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        response = client.get(
            f"/api/v1/leave-applications/{app.pk}/tracking/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        states = {row["order"]: row["state"] for row in response.data["stages"]}
        self.assertEqual(
            [states[order] for order in (1, 2, 3)],
            ["awaiting", "upcoming", "upcoming"],
        )

    def test_the_full_chain_completes_for_an_approver_applicant(self):
        app = self.submit()
        self.approve(app, self.supervisor)
        self.approve(app, self.other_hod)
        self.approve(app, self.registrar)

        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(
            [s.status for s in app.stages.order_by("stage_order")],
            [
                ApplicationStage.Status.APPROVED,
                ApplicationStage.Status.APPROVED,
                ApplicationStage.Status.APPROVED,
            ],
        )


class SoleMemberStageIsSkippedTests(SelfApprovalBase):
    """A stage staffed only by the applicant is skipped, not routed to a stand-in.

    The reported cases: the applicant is the only HOD, or the only Registrar. Their
    own stage is materialised as skipped with a reason, every stage below it is
    skipped for being below them, and the application opens at the first stage
    above (Unit 30). This replaces the old behaviour, which refused the
    submission outright.
    """

    def assertSkipped(self, *orders, reasons=()):
        app = self.submit()
        for order in orders:
            stage = self.stage_at(app, order)
            self.assertEqual(
                stage.status,
                ApplicationStage.Status.SKIPPED,
                f"stage {order} should be skipped",
            )
            self.assertEqual(
                stage.eligible_approver_ids(), (), f"stage {order} resolves nobody"
            )
        for order, reason in reasons:
            self.assertEqual(self.stage_at(app, order).skip_reason, reason)
        app.refresh_from_db()
        # The application still opened somewhere, so it is in flight rather than
        # stuck: exactly one stage is pending, and it is above everything skipped.
        pending = [
            s for s in app.stages.all() if s.status == ApplicationStage.Status.PENDING
        ]
        self.assertEqual(len(pending), 1, "exactly one stage opens pending")
        self.assertEqual(app.current_stage_id, pending[0].id)
        # The stage that opened is *above* everything skipped, never one of them.
        self.assertGreater(pending[0].stage_order, min(orders))
        return app

    def test_the_only_hod_being_the_applicant_opens_at_the_registrar(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)

        app = self.assertSkipped(
            1,
            2,
            reasons=(
                (1, "Applicant is a higher-stage approver."),
                (2, "Applicant cannot approve their own application."),
            ),
        )

        self.assertEqual(app.current_stage.role, "registrar")

    def test_the_only_registrar_being_the_applicant_is_handed_to_hr(self):
        """The applicant is the last stage, so there is nothing above to open at
        and HR decides it instead."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.employee)

        app = self.assertSkipped(1, 2, 3)

        self.assertEqual(app.current_stage.role, "hr")
        self.assertEqual(app.current_stage.role_label, "Human Resources")

    def test_the_applicants_stage_is_skipped_not_dropped(self):
        """The distinction that matters: skipped rather than routed to a
        stand-in, and not silently dropped either -- it stays in the history with
        the reason attached."""
        self.stub.workflow.set_chain("hod")
        self.staff_role("hod", self.employee)

        app = self.submit()

        skipped = self.stage_at(app, 1)
        self.assertEqual(skipped.status, ApplicationStage.Status.SKIPPED)
        self.assertEqual(
            skipped.skip_reason, "Applicant cannot approve their own application."
        )
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_stage.role, "hr")

    def test_the_applicant_is_never_in_the_eligibility_of_any_stage(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        for stage in app.stages.all():
            self.assertNotIn(self.employee.id, stage.eligible_approver_ids())

    def test_hr_decides_the_handed_over_application(self):
        """The applicant's own position was the last step, so HR is what is left
        to decide -- through the same stage machinery as any other step."""
        self.stub.workflow.set_chain("hod")
        self.staff_role("hod", self.employee)

        app = self.submit()

        self.approve(app, self.hr)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertEqual(self.stage_at(app, 2).status, ApplicationStage.Status.APPROVED)

    def test_the_skip_is_audited(self):
        """The audit trail has to explain why the chain starts where it does. The
        applicant is the actor: their own position is what caused it."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        entries = AuditEntry.objects.filter(
            action=AuditEntry.Action.STAGE_SKIPPED,
            target_id=str(app.pk),
        )
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.actor_id, self.employee.id)
        self.assertEqual(
            [stage["order"] for stage in entry.detail["stages"]], [1, 2]
        )
        self.assertEqual(
            entry.detail["stages"][1]["reason"],
            "Applicant cannot approve their own application.",
        )
        self.assertIn("2", entry.target_summary)

    def test_nothing_is_audited_when_nothing_was_skipped(self):
        """An ordinary chain must not manufacture a skip entry."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        self.assertFalse(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.STAGE_SKIPPED
            ).exists()
        )

    def test_the_api_shows_the_skipped_stages_with_their_reason(self):
        """A reader has to be able to tell a deliberate skip from a stage that
        was quietly dropped, so both the review payload and the employee-facing
        tracking payload carry the reason."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)
        app = self.submit()

        client = APIClient()
        client.force_authenticate(user=self.registrar)
        review = client.get(f"/api/v1/approvals/{app.pk}/")
        self.assertEqual(review.status_code, status.HTTP_200_OK)
        stages = {row["order"]: row for row in review.data["workflow"]["stages"]}
        self.assertEqual(stages[1]["status"], "skipped")
        self.assertEqual(
            stages[1]["skip_reason"], "Applicant is a higher-stage approver."
        )
        self.assertEqual(
            stages[2]["skip_reason"], "Applicant cannot approve their own application."
        )
        self.assertIsNone(stages[3]["skip_reason"])

        client.force_authenticate(user=self.employee)
        tracking = client.get(f"/api/v1/leave-applications/{app.pk}/tracking/")
        self.assertEqual(tracking.status_code, status.HTTP_200_OK)
        tracked = {row["order"]: row for row in tracking.data["stages"]}
        self.assertEqual(tracked[1]["state"], "skipped")
        self.assertEqual(
            tracked[2]["state"], "skipped"
        )
        self.assertEqual(
            tracked[2]["skip_reason"], "Applicant cannot approve their own application."
        )
        self.assertEqual(tracked[3]["state"], "awaiting")
        self.assertIsNone(tracked[3]["skip_reason"])

    def test_a_skipped_stage_never_reaches_an_approvers_queue(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)
        app = self.submit()

        client = APIClient()
        client.force_authenticate(user=self.registrar)
        client.get(f"/api/v1/approvals/?tab=pending")

        pending = client.get("/api/v1/approvals/?tab=pending").data["results"]
        rows = [row for row in pending if row["id"] == str(app.pk)]
        self.assertEqual(len(rows), 1)

    def test_the_applicant_cannot_decide_the_hr_stage_themselves(self):
        self.stub.workflow.set_chain("hod")
        self.staff_role("hod", self.employee)

        app = self.submit()

        with self.assertRaises(ApprovalNotAllowedError) as caught:
            self.approve(app, self.employee)
        self.assertEqual(caught.exception.reason, "self_application")
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)


class UnstaffedStageIsStillRefusedTests(SelfApprovalBase):
    """A stage nobody staffs at all is a configuration error, not a skip.

    Distinct from the applicant holding a stage: here the section simply has
    nobody, so there is no applicant to blame and nowhere to send it. The
    submission is refused and the message names the stranded step.
    """

    def setUp(self):
        super().setUp()
        self.stub.workflow.strict = True

    def test_an_unstaffed_stage_refuses_the_submission(self):
        self.stub.workflow.set_chain("supervisor", "hod")
        self.staff_role("supervisor", self.supervisor)
        # "hod" deliberately left empty.

        self.assertRefused("Head of Department")

    def test_an_unstaffed_stage_at_the_top_refuses_the_submission(self):
        self.stub.workflow.set_chain("supervisor")
        self.assertRefused("Supervisor")

    def test_the_refusal_says_what_would_fix_it(self):
        """The remedy is staffing, not a different role: the section itself is
        fine, it just has nobody in it who may act."""
        self.stub.workflow.set_chain("supervisor", "hod")
        self.staff_role("supervisor", self.supervisor)

        message = self.assertRefused("Head of Department")
        self.assertIn("No active approver", message)

    def test_the_refusal_reaches_the_api_as_422_workflow_unavailable(self):
        self.stub.workflow.set_chain("hod")
        app = self.draft()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        response = client.post(f"/api/v1/leave-applications/{app.pk}/submit/")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_FAILED")
        self.assertIn(
            "workflow_unavailable", {e["code"] for e in response.data["errors"]}
        )

    def test_no_stage_is_created_for_a_refused_submission(self):
        self.stub.workflow.set_chain("hod")
        app = self.draft()

        with self.assertRaises(ValidationFailedError):
            submit_application(user=self.employee, application_id=app.pk)

        self.assertEqual(app.stages.count(), 0)

    def test_a_plain_employee_is_unaffected(self):
        """The gate is the applicant's own membership, not their job title."""
        self.stub.workflow.set_chain("supervisor", "hod")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        plain_user = make_user("plain@selfapproval", first_name="Pa", last_name="Plain")
        self.stub.register_employee(plain_user)
        app = LeaveApplication.objects.create(
            employee=plain_user,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )

        submit_application(user=plain_user, application_id=app.pk)
        app.refresh_from_db()

        self.assertEqual(app.current_stage.stage_order, 1)
        self.assertEqual(
            self.stage_at(app, 1).eligible_approver_ids(), (self.supervisor.id,)
        )


class DelegationDoesNotSatisfyTheRule(SelfApprovalBase):
    """A delegate on the applicant's own account does not make them an approver."""

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("hod", "supervisor", "registrar")
        self.staff_role("hod", self.employee)
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("registrar", self.registrar)
        today = timezone.localdate()
        self.delegation = Delegation.objects.create(
            approver=self.employee,
            delegate=self.supervisor,
            starts_on=today - timedelta(days=1),
            ends_on=today + timedelta(days=5),
            status=Delegation.Status.APPROVED,
            requested_by=self.employee,
            decided_by=self.hr,
            decision_reason="Cover",
        )

    def test_the_stage_is_skipped_rather_than_routed_to_their_delegate(self):
        """Their cover does not put them back in their own section's decision
        set: the eligibility snapshot is the section's members minus the
        applicant, and a delegate of the applicant is somebody else entirely. So
        the stage resolves to nobody and is skipped (Unit 30), and the application
        opens at the supervisor -- not at the person covering for the applicant."""
        app = self.submit()

        skipped = self.stage_at(app, 1)
        self.assertEqual(skipped.status, ApplicationStage.Status.SKIPPED)
        self.assertEqual(
            skipped.skip_reason, "Applicant cannot approve their own application."
        )
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_stage.role, "supervisor")

    def test_the_supervisor_never_sees_it(self):
        app = self.draft()
        client = APIClient()
        client.force_authenticate(user=self.supervisor)

        client.post(f"/api/v1/leave-applications/{app.pk}/submit/")

        pending = client.get("/api/v1/approvals/?tab=pending").data["results"]
        self.assertNotIn(str(app.pk), [row["id"] for row in pending])

    def test_sharing_the_section_with_the_applicant_still_routes_to_the_colleague(self):
        """With a second HOD added, the section routes — and not to the applicant
        or to their delegate-by-proxy."""
        self.staff_role("hod", self.other_hod)

        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).eligible_approver_ids(), (self.other_hod.id,)
        )
        client = APIClient()
        client.force_authenticate(user=self.supervisor)
        pending = client.get("/api/v1/approvals/?tab=pending").data["results"]
        self.assertNotIn(str(app.pk), [row["id"] for row in pending])


class AdvanceTimeBlockIsDefenseInDepth(SelfApprovalBase):
    """Rows that predate sections, or a chain reconfigured after submission.

    ``assign_workflow`` now refuses an unsatisfiable section at submission, so
    the only way to reach the advance-time block is an application whose later
    stages have no eligible approver — one materialised before sections, or one
    whose stage rows were emptied. It must still refuse rather than advance, and
    it must roll the decision back.
    """

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)

    def stranded_row(self):
        """A routable application whose next stage has nobody who can act."""
        app = self.submit()
        self.stage_at(app, 2).eligible_approvers.all().delete()
        return app

    def test_advance_is_refused(self):
        app = self.stranded_row()

        with self.assertRaises(SelfApprovalBlockedError):
            self.approve(app, self.supervisor)

    def test_refused_advance_rolls_the_decision_back(self):
        app = self.stranded_row()
        version_before = self.stage_at(app, 1).decision_version

        with self.assertRaises(SelfApprovalBlockedError):
            self.approve(app, self.supervisor)

        app.refresh_from_db()
        self.assertFalse(ApprovalDecision.objects.filter(application=app).exists())
        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.PENDING
        )
        self.assertEqual(
            self.stage_at(app, 1).decision_version, version_before
        )
        # Nobody had claimed the open section, so there was nothing to restore
        # to — the refused advance left the spine exactly as it found it.
        self.assertIsNone(app.current_approver_id)
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)

    def test_api_surfaces_the_refusal_as_409_workflow_unavailable(self):
        app = self.stranded_row()
        client = APIClient()
        client.force_authenticate(user=self.supervisor)

        response = client.post(
            f"/api/v1/approvals/{app.pk}/decision/",
            {"action": "approve", "stage_version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["reason"], "workflow_unavailable")
        self.assertIn("nobody can act", response.data["error"])
        self.assertIn("Human Resources", response.data["error"])

    def test_reassigning_the_current_approver_does_not_help(self):
        """The remedy the message points at is staffing, not a spine move, so
        moving the current approver must genuinely not unblock it."""
        app = self.stranded_row()
        reassign_application(
            application=app, to_approver=self.dvc, actor=self.hr, reason="Cover"
        )

        with self.assertRaises(SelfApprovalBlockedError):
            decide(
                application_id=app.pk,
                actor=self.dvc,
                action=ApprovalDecision.Action.APPROVE,
                expected_version=1,
            )


class SharedCheckIsUsedEverywhere(SelfApprovalBase):
    """Reassignment and the decision guard refuse the applicant via the one check."""

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("supervisor", "hod")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)

    def test_predicate_accepts_a_user_or_an_id(self):
        app = self.submit()

        self.assertTrue(is_self_application(self.employee, app))
        self.assertTrue(is_self_application(self.employee.id, app))
        self.assertFalse(is_self_application(self.supervisor, app))
        self.assertFalse(is_self_application(self.supervisor.id, app))
        self.assertFalse(is_self_application(None, app))

    def test_reassignment_to_the_applicant_is_refused(self):
        app = self.submit()

        with self.assertRaises(ReassignmentError) as caught:
            reassign_application(
                application=app,
                to_approver=self.employee,
                actor=self.hr,
                reason="Coverage",
            )

        app.refresh_from_db()
        self.assertIn("own", str(caught.exception).lower())
        self.assertIsNone(app.current_approver_id)
        self.assertFalse(Reassignment.objects.filter(application=app).exists())

    def test_a_row_pointing_at_the_applicant_is_still_denied_authority(self):
        """The guard is independent of the snapshot.

        A pre-sections row may still name the applicant on a live stage, and a
        reassignment may have pointed the spine at them. Authority refuses them
        anyway, because it is the one check every path goes through.
        """
        app = self.submit()
        live = self.stage_at(app, 1)
        live.assigned_approver = self.employee
        live.save(update_fields=["assigned_approver"])
        app.current_approver = self.employee
        app.save(update_fields=["current_approver"])

        authority = get_decision_authority(self.employee, app)

        self.assertFalse(authority.can_decide)
        self.assertEqual(authority.reason, "self_application")
