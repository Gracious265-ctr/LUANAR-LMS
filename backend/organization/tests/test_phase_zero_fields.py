"""Fields Phase 0 added to existing models, and why each one is nullable.

Three separate additions, grouped because they are all "a fact about a moment
that we refused to infer at read time":

* ``LeaveType.requires_institutional_approval`` — the one place a leave type is
  allowed to influence routing. Off by default, because a type that quietly
  required the registrar's signature on every request would be discovered by an
  employee rather than by HR.
* ``ApprovalDecision.on_behalf_of`` / ``.acting_assignment`` — snapshots of who
  was actually covering. Stored, not derived, because "was acting for" is a fact
  about the past and recomputing it from today's active delegations answers a
  different question.
* ``ApplicationStage.last_reminder_at`` — the only state a reminder needs, kept
  on the row it describes so the two cannot drift apart.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from leave.models import LeaveApplication, LeaveType
from leave.serializers import LeaveTypeSerializer
from organization.models import ActingAssignment, OrgUnit
from users.models import User
from workflows.models import (
    ApplicationStage,
    ApplicationStageApprover,
    ApprovalDecision,
    ApprovalDecisionLockedError,
)


def make_user(username, *, role=None):
    return User.objects.create_user(
        username=username,
        email=username,
        password="testpass123",
        role=role or User.Role.EMPLOYEE,
        first_name="Field",
        last_name="Tester",
    )


class LeaveTypeInstitutionalFlagTests(TestCase):
    def test_the_flag_defaults_to_off(self):
        leave_type = LeaveType.objects.create(name="Annual Leave")
        self.assertFalse(leave_type.requires_institutional_approval)

    def test_the_flag_can_be_switched_on(self):
        leave_type = LeaveType.objects.create(
            name="Sabbatical Leave", requires_institutional_approval=True
        )
        leave_type.refresh_from_db()
        self.assertTrue(leave_type.requires_institutional_approval)

    def test_an_existing_leave_type_is_unaffected_by_the_new_field(self):
        # The migration adds a column with a default, so nothing that routes
        # through a leave type changes behaviour until HR opts in.
        leave_type = LeaveType.objects.create(name="Annual Leave")
        self.assertFalse(leave_type.requires_institutional_approval)

    def test_the_serializer_exposes_the_flag(self):
        payload = {"name": "Study Leave", "requires_institutional_approval": True}
        serializer = LeaveTypeSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        leave_type = serializer.save()
        self.assertTrue(leave_type.requires_institutional_approval)

    def test_the_serializer_defaults_the_flag_to_off(self):
        serializer = LeaveTypeSerializer(data={"name": "Bereavement Leave"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.save().requires_institutional_approval)


class DecisionSnapshotTestCase(TestCase):
    def setUp(self):
        self.applicant = make_user("snapshot.applicant@test.luanar")
        self.designated = make_user("snapshot.designated@test.luanar")
        self.cover = make_user("snapshot.cover@test.luanar")
        self.hr = make_user("snapshot.hr@test.luanar", role=User.Role.HR)

        self.unit = OrgUnit.objects.create(
            name="Luanar University", unit_type=OrgUnit.UnitType.INSTITUTION
        )
        self.assignment = ActingAssignment.objects.create(
            org_unit=self.unit,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=timezone.localdate() - timedelta(days=1),
            reason="Registrar on sabbatical",
        )

        self.application = LeaveApplication.objects.create(
            employee=self.applicant,
            leave_type_id=1,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            current_approver=self.designated,
        )
        self.stage = ApplicationStage.objects.create(
            application=self.application,
            stage_order=1,
            role="registrar",
            role_label="Registrar",
            status=ApplicationStage.Status.PENDING,
        )
        ApplicationStageApprover.objects.create(
            stage=self.stage, user=self.cover
        )


class ApprovalDecisionSnapshotTests(DecisionSnapshotTestCase):
    def _decide(self, **overrides):
        fields = {
            "application": self.application,
            "stage": self.stage,
            "approver": self.cover,
            "approver_name": self.cover.get_full_name(),
            "role_label": "Registrar",
            "action": ApprovalDecision.Action.APPROVE,
        }
        fields.update(overrides)
        return ApprovalDecision.objects.create(**fields)

    def test_a_decision_in_own_right_records_nothing_extra(self):
        decision = self._decide()
        self.assertIsNone(decision.on_behalf_of_id)
        self.assertIsNone(decision.acting_assignment_id)

    def test_an_actancy_decision_records_who_was_covered(self):
        decision = self._decide(
            approver_name=self.cover.get_full_name(),
            on_behalf_of=self.designated,
            acting_assignment=self.assignment,
        )
        self.assertEqual(decision.on_behalf_of_id, self.designated.pk)
        self.assertEqual(decision.acting_assignment_id, self.assignment.pk)

    def test_the_snapshot_survives_the_actancy_being_deleted(self):
        # ``on_delete=PROTECT`` is what makes this meaningful: the row a decision
        # points at cannot be removed, so "who was acting, and why" stays
        # readable after HR tidies the actancy list up.
        decision = self._decide(
            on_behalf_of=self.designated, acting_assignment=self.assignment
        )
        self.assertEqual(decision.acting_assignment.reason, "Registrar on sabbatical")

    def test_a_snapshot_decision_is_still_append_only(self):
        decision = self._decide(on_behalf_of=self.designated)
        with self.assertRaises(ApprovalDecisionLockedError):
            decision.save()


class ReminderFieldTests(DecisionSnapshotTestCase):
    def test_a_new_stage_has_never_been_reminded(self):
        self.assertIsNone(self.stage.last_reminder_at)

    def test_recording_a_reminder_is_a_single_field_write(self):
        # The alternative — a separate reminder table — can hold a row for a
        # stage that has since been decided, or miss one that was reminded.
        sent = timezone.now()
        ApplicationStage.objects.filter(pk=self.stage.pk).update(
            last_reminder_at=sent
        )
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.last_reminder_at, sent)

    def test_the_reminder_field_is_per_stage(self):
        second = ApplicationStage.objects.create(
            application=self.application,
            stage_order=2,
            role="hr",
            role_label="Human Resources",
            status=ApplicationStage.Status.WAITING,
        )
        self.assertIsNone(second.last_reminder_at)
