"""The self-approval business rule: an applicant is never an approver of record.

Covers the two places the rule bites:

* **assignment** — a stage whose configured approver is the applicant is
  skipped when a later stage has a valid approver, and blocks outright when none
  does;
* **advancement** — the same resolution runs again every time the chain advances,
  which also covers applications submitted before the rule existed.

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

from .models import (
    ApplicationStage,
    ApprovalDecision,
    Delegation,
    Reassignment,
)
from .policies import get_decision_authority, is_self_application
from .services import (
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
    """The applicant also holds a real approver role, so a stage can match them."""

    def setUp(self):
        self.stub = self.use_stub()
        self.employee = make_user(
            "emp@selfapproval",
            role=User.Role.HOD,
            first_name="Nia",
            last_name="Applicant",
        )
        self.supervisor = make_user(
            "sup@selfapproval",
            role=User.Role.SUPERVISOR,
            first_name="Sam",
            last_name="Supervisor",
        )
        self.other_hod = make_user(
            "hod2@selfapproval",
            role=User.Role.HOD,
            first_name="Hana",
            last_name="OtherHod",
        )
        self.registrar = make_user(
            "reg@selfapproval",
            role=User.Role.REGISTRAR,
            first_name="Rio",
            last_name="Registrar",
        )
        self.dvc = make_user(
            "dvc@selfapproval",
            role=User.Role.DVC,
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
            department="Administration",
            grade="B",
        )

    def staff_role(self, role, user):
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

    def stage_audit(self, app, order):
        entry = AuditEntry.objects.filter(
            target_type="application",
            target_id=str(app.pk),
            action=AuditEntry.Action.STAGE_SKIPPED,
        ).first()
        self.assertIsNotNone(entry, f"no STAGE_SKIPPED audit entry for {app.pk}")
        skipped = entry.detail["skipped_stages"]
        self.assertIn(order, [row["order"] for row in skipped])
        return entry


class LeadingSelfStageTests(SelfApprovalBase):
    """A first-stage self match is skipped while the chain is built."""

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("hod", "supervisor", "registrar")
        self.staff_role("hod", self.employee)
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("registrar", self.registrar)

    def test_leading_self_stage_is_skipped_and_next_stage_goes_live(self):
        app = self.submit()

        skipped = self.stage_at(app, 1)
        self.assertEqual(skipped.status, ApplicationStage.Status.SKIPPED)
        self.assertEqual(skipped.assigned_approver_id, self.employee.id)
        self.assertEqual(skipped.decision_version, 1)
        self.assertFalse(ApprovalDecision.objects.filter(stage=skipped).exists())

        live = self.stage_at(app, 2)
        self.assertEqual(live.status, ApplicationStage.Status.PENDING)
        self.assertEqual(live.assigned_approver_id, self.supervisor.id)

        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_approver_id, self.supervisor.id)

    def test_skip_is_audited_with_the_reference_number(self):
        app = self.submit()

        entry = self.stage_audit(app, 1)
        self.assertEqual(entry.target_summary, app.reference_number)
        self.assertIsNone(entry.actor_id)
        self.assertEqual(entry.detail["reason"], "applicant_is_the_approver")
        self.assertEqual(
            entry.detail["skipped_stages"][0]["assigned_approver_id"],
            self.employee.id,
        )
        self.assertEqual(entry.detail["activated_stage_order"], 2)
        self.assertEqual(entry.detail["activated_role_label"], "Supervisor")

    def test_applicant_is_never_offered_the_skipped_stage(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        pending = client.get("/api/v1/approvals/?tab=pending").data["results"]
        self.assertNotIn(str(app.pk), [row["id"] for row in pending])
        self.assertFalse(get_decision_authority(self.employee, app).can_decide)
        self.assertEqual(
            get_decision_authority(self.employee, app).reason, "self_application"
        )


class ApplicantInTheMiddleOfTheChainTests(SelfApprovalBase):
    """``supervisor -> HOD -> Registrar -> DVC`` with the applicant as HOD.

    The applicant's own stage is removed from the path, and so is everything
    below it: the application starts at the Registrar, never at the Supervisor.
    """

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("supervisor", "hod", "registrar", "dvc")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)
        self.staff_role("dvc", self.dvc)

    def test_the_flow_starts_after_the_applicant_not_at_the_beginning(self):
        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 2).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 3).status, ApplicationStage.Status.PENDING
        )
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 3)
        self.assertEqual(app.current_approver_id, self.registrar.id)

    def test_the_supervisor_is_never_asked_to_approve_it(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.supervisor)

        response = client.get(f"/api/v1/approvals/{app.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_skip_is_audited_with_the_reason_per_stage(self):
        app = self.submit()

        entry = self.stage_audit(app, 2)
        self.assertIsNone(entry.actor_id)
        self.assertEqual(entry.detail["applicant_stage_orders"], [2])
        reasons = {
            row["order"]: row["skip_reason"]
            for row in entry.detail["skipped_stages"]
        }
        self.assertEqual(reasons[1], "before_applicant_stage")
        self.assertEqual(reasons[2], "applicant_is_approver")
        self.assertEqual(entry.detail["activated_stage_order"], 3)
        self.assertEqual(entry.detail["activated_role_label"], "Registrar")

    def test_consecutive_self_stages_are_all_skipped(self):
        self.staff_role("registrar", self.employee)
        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 2).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 3).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 4).status, ApplicationStage.Status.PENDING
        )
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.dvc.id)
        self.assertEqual(
            self.stage_audit(app, 3).detail["applicant_stage_orders"], [2, 3]
        )

    def test_next_stage_label_names_the_stage_that_will_really_receive_it(self):
        """The approve dialog must not advertise the applicant's own stage."""
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.registrar)

        response = client.get(f"/api/v1/approvals/{app.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["workflow"]["current_stage"]["next_role_label"],
            "Deputy Vice-Chancellor",
        )

    def test_reviewer_sees_the_skipped_stages_in_the_timeline(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.registrar)

        response = client.get(f"/api/v1/approvals/{app.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stages = {row["order"]: row for row in response.data["workflow"]["stages"]}
        self.assertEqual(stages[1]["status"], "skipped")
        self.assertEqual(stages[1]["assigned_approver"], "Sam Supervisor")
        self.assertEqual(stages[2]["status"], "skipped")
        self.assertEqual(stages[2]["assigned_approver"], "Nia Applicant")
        self.assertEqual(stages[2]["decided_at"], None)
        self.assertEqual(stages[3]["status"], "pending")
        self.assertEqual(stages[3]["assigned_approver"], "Rio Registrar")

    def test_tracking_reports_the_skipped_states(self):
        app = self.submit()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        response = client.get(
            f"/api/v1/leave-applications/{app.pk}/tracking/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        states = {row["order"]: row["state"] for row in response.data["stages"]}
        self.assertEqual(states[1], "skipped")
        self.assertEqual(states[2], "skipped")
        self.assertEqual(states[3], "awaiting")
        self.assertEqual(states[4], "upcoming")


class FinalStageIsTheApplicant(SelfApprovalBase):
    """The configured final stage must be able to sign off, or nothing routes.

    A role resolves to one approver (the lowest-id active holder), so when the
    applicant *is* that holder and the stage is last, nobody is left to approve
    their own leave. The application is refused at submission instead of being
    routed into a chain that cannot finish.
    """

    def draft(self):
        return LeaveApplication.objects.create(
            employee=self.employee,
            end_date=EARLIEST_ANNUAL_START + timedelta(days=3),
            **ANNUAL,
        )

    def assertRefused(self):
        app = self.draft()
        with self.assertRaises(ValidationFailedError) as caught:
            submit_application(user=self.employee, application_id=app.pk)
        self.assertEqual(caught.exception.errors[0].code, "workflow_unavailable")
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.DRAFT)
        self.assertEqual(app.stages.count(), 0)
        return caught.exception.errors[0].message

    def test_high_level_applicant_with_no_later_approver_is_refused(self):
        """The reported case: the applicant is the only Registrar, and it is last."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.employee)

        message = self.assertRefused()

        self.assertIn("approver for the Registrar stage", message)
        self.assertIn("which is the last stage", message)
        self.assertIn("no later approver", message)

    def test_low_level_applicant_with_no_later_approver_is_refused(self):
        self.stub.workflow.set_chain("supervisor", "hod")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)

        message = self.assertRefused()

        self.assertIn(
            "approver for the Head of Department stage", message
        )

    def test_consecutive_final_stages_holding_the_applicant_are_refused(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.employee)

        self.assertIn(
            "approver for the Head of Department, Registrar stage",
            self.assertRefused(),
        )

    def test_every_stage_resolving_to_the_applicant_blocks_assignment(self):
        self.stub.workflow.set_chain("hod", "registrar")
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.employee)

        self.assertIn("every stage", self.assertRefused())

    def test_refusal_reaches_the_api_as_422_workflow_unavailable(self):
        self.stub.workflow.set_chain("hod")
        self.staff_role("hod", self.employee)
        app = self.draft()
        client = APIClient()
        client.force_authenticate(user=self.employee)

        response = client.post(f"/api/v1/leave-applications/{app.pk}/submit/")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_FAILED")
        self.assertIn(
            "workflow_unavailable", {e["code"] for e in response.data["errors"]}
        )

    def test_refusal_never_promises_an_impossible_reassignment(self):
        """Reassignment only moves the current approver, so it cannot unblock a
        later stage. The message must not offer it as the remedy."""
        self.stub.workflow.set_chain("supervisor", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("registrar", self.employee)

        message = self.assertRefused()

        self.assertNotIn("reassign the application", message)
        self.assertIn("different approver role", message)

    def test_low_level_applicant_still_routes_forward_to_the_next_approver(self):
        """The applicant's stage is dropped from the path, never the start of it."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.employee)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        self.assertEqual(self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED)
        self.assertEqual(self.stage_at(app, 2).status, ApplicationStage.Status.PENDING)
        app.refresh_from_db()
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_approver_id, self.other_hod.id)

    def test_high_level_applicant_with_a_later_approver_completes_at_the_top(self):
        self.stub.workflow.set_chain("supervisor", "registrar", "dvc")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("registrar", self.employee)
        self.staff_role("dvc", self.dvc)

        app = self.submit()

        # The application never reaches the Supervisor, who sits below the
        # applicant; it goes straight to the DVC, the stage after them.
        self.assertEqual(app.current_stage.stage_order, 3)
        self.assertEqual(app.current_approver_id, self.dvc.id)
        self.approve(app, self.dvc)
        app.refresh_from_db()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 2).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(self.stage_at(app, 3).status, ApplicationStage.Status.APPROVED)
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)
        self.assertTrue(app.current_stage.is_final)

    def test_the_hod_example_from_the_rule(self):
        """``supervisor -> HOD -> Registrar``: the HOD's application goes to the
        Registrar, not to the Supervisor, because the Supervisor is lower down
        the queue than the applicant."""
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.employee)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        self.assertEqual(app.current_stage.stage_order, 3)
        self.assertEqual(app.current_approver_id, self.registrar.id)
        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(
            self.stage_at(app, 2).status, ApplicationStage.Status.SKIPPED
        )
        self.approve(app, self.registrar)
        app.refresh_from_db()
        self.assertEqual(app.status, LeaveApplication.Status.APPROVED)

    def test_a_plain_employee_still_starts_at_the_first_stage(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)
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
        self.assertEqual(app.current_approver_id, self.supervisor.id)
        self.assertEqual(app.stages.filter(status="skipped").count(), 0)

    def test_supervisors_own_application_goes_to_the_hod(self):
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.employee)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)

        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        self.assertEqual(app.current_stage.stage_order, 2)
        self.assertEqual(app.current_approver_id, self.other_hod.id)


class AdvanceTimeBlockIsDefenseInDepth(SelfApprovalBase):
    """Rows that predate the rule, or a chain reconfigured after submission.

    ``assign_workflow`` now refuses these at submission, so the only way to
    reach the advance-time block is an application routed under the old rules
    (or under a workflow that changed afterwards). It must still refuse rather
    than route to the applicant, and it must roll the decision back.
    """

    def setUp(self):
        super().setUp()
        self.stub.workflow.set_chain("supervisor", "hod", "registrar")
        self.staff_role("supervisor", self.supervisor)
        self.staff_role("hod", self.other_hod)
        self.staff_role("registrar", self.registrar)

    def legacy_row(self):
        """A routable application whose later stages now point at the applicant.

        The chain was valid when it was submitted; afterwards every stage from
        the current one onward resolved to the applicant, which is what
        ``assign_workflow`` now prevents up front.
        """
        app = self.submit()
        for order in (2, 3):
            stage = self.stage_at(app, order)
            stage.assigned_approver = self.employee
            stage.save(update_fields=["assigned_approver"])
        return app

    def test_advance_is_refused(self):
        app = self.legacy_row()

        with self.assertRaises(SelfApprovalBlockedError):
            self.approve(app, self.supervisor)

    def test_refused_advance_rolls_the_decision_back(self):
        app = self.legacy_row()
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
        self.assertEqual(app.current_approver_id, self.supervisor.id)
        self.assertEqual(app.status, LeaveApplication.Status.SUBMITTED)
        self.assertFalse(
            AuditEntry.objects.filter(
                action=AuditEntry.Action.STAGE_SKIPPED
            ).exists()
        )

    def test_api_surfaces_the_refusal_as_409_workflow_unavailable(self):
        app = self.legacy_row()
        client = APIClient()
        client.force_authenticate(user=self.supervisor)

        response = client.post(
            f"/api/v1/approvals/{app.pk}/decision/",
            {"action": "approve", "stage_version": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["reason"], "workflow_unavailable")
        self.assertIn("own leave application", response.data["error"])
        self.assertIn("will not help", response.data["error"])

    def test_reassigning_the_current_approver_does_not_help(self):
        """The remedy the message rules out must genuinely be useless."""
        app = self.legacy_row()
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


class DelegationDoesNotSatisfyTheRule(SelfApprovalBase):
    """A delegate on the applicant's own account does not make them a valid approver."""

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

    def test_self_stage_is_skipped_even_with_an_active_delegation(self):
        app = self.submit()

        self.assertEqual(
            self.stage_at(app, 1).status, ApplicationStage.Status.SKIPPED
        )
        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.supervisor.id)


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
        self.assertEqual(app.current_approver_id, self.supervisor.id)
        self.assertFalse(Reassignment.objects.filter(application=app).exists())

    def test_legacy_self_stage_is_still_denied_authority(self):
        """A pre-rule row may still hold the applicant; the guard is independent."""
        app = self.submit()
        waiting = self.stage_at(app, 1)
        live = self.stage_at(app, 2)
        waiting.status = ApplicationStage.Status.SUPERSEDED
        waiting.save(update_fields=["status"])
        live.status = ApplicationStage.Status.PENDING
        live.assigned_approver = self.employee
        live.save(update_fields=["status", "assigned_approver"])
        app.current_stage = live
        app.current_approver = self.employee
        app.save(update_fields=["current_stage", "current_approver"])

        authority = get_decision_authority(self.employee, app)

        self.assertFalse(authority.can_decide)
        self.assertEqual(authority.reason, "self_application")
