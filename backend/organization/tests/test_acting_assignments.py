"""The actancy that temporarily covers an absent approver.

Two things are worth pinning here. The first is that a seat can only have one
person in it at a time, and that the rule survives two HR users saving at once —
an overlap left in the database is indistinguishable from nobody knowing who is
in charge, so it has to be refused rather than rendered as "one of these".

The second is that an actancy never *revokes* anything. It widens who may act
while it runs and stops there; the departments it covers keep whatever authority
the eligibility snapshot gave them. That asymmetry is deliberate and matches how
the approval engine already treats membership that ends today.
"""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from organization.exceptions import ActingAssignmentConflictError
from organization.models import ActingAssignment, OrgUnit
from organization.services import (
    create_acting_assignment,
    covering_acting_assignment,
)
from users.models import User
from workflows.models import ApproverRole


def make_user(username, *, role=None):
    return User.objects.create_user(
        username=username,
        email=username,
        password="testpass123",
        role=role or User.Role.HR,
        first_name="Acting",
        last_name="Tester",
    )


class ActingTestCase(TestCase):
    def setUp(self):
        self.institution = OrgUnit.objects.create(
            name="Luanar University", unit_type=OrgUnit.UnitType.INSTITUTION
        )
        self.department = OrgUnit.objects.create(
            name="Department of Computer Science",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )
        self.dean_role = ApproverRole.objects.create(code="act_dean", label="Dean")
        self.head = make_user("acting.head@test.luanar")
        self.cover = make_user("acting.cover@test.luanar")
        self.hr = make_user("acting.hr@test.luanar")
        self.today = timezone.localdate()


class OneSeatOnePersonTests(ActingTestCase):
    def test_an_actancy_names_either_a_person_or_a_role(self):
        assignment = ActingAssignment.objects.create(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today,
            reason="HOD on study leave",
        )
        self.assertEqual(assignment.state, "active")
        self.assertIn("Department of Computer Science", str(assignment))

    def test_naming_neither_a_person_nor_a_role_is_refused_by_the_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ActingAssignment.objects.create(
                    org_unit=self.department,
                    created_by=self.hr,
                    start_date=self.today,
                )

    def test_naming_both_is_refused_by_the_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ActingAssignment.objects.create(
                    org_unit=self.department,
                    acting_user=self.cover,
                    role=self.dean_role,
                    created_by=self.hr,
                    start_date=self.today,
                )

    def test_an_end_before_the_start_is_refused_by_the_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ActingAssignment.objects.create(
                    org_unit=self.department,
                    acting_user=self.cover,
                    created_by=self.hr,
                    start_date=self.today,
                    end_date=self.today - timedelta(days=1),
                )


class SingleWriterValidationTests(ActingTestCase):
    """What ``full_clean()`` refuses before a row is ever attempted.

    The database constraints above are the backstop; these are the messages an
    HR user actually sees. They matter because they run *before* the write, so a
    refused booking cannot leave a half-made actancy behind.
    """

    def test_naming_neither_target_is_refused_with_a_readable_message(self):
        assignment = ActingAssignment(
            org_unit=self.department,
            created_by=self.hr,
            start_date=self.today,
        )
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("role", caught.exception.error_dict)

    def test_naming_both_targets_is_refused(self):
        assignment = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            role=self.dean_role,
            created_by=self.hr,
            start_date=self.today,
        )
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("role", caught.exception.error_dict)

    def test_an_end_before_the_start_is_refused(self):
        assignment = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today,
            end_date=self.today - timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("end_date", caught.exception.error_dict)

    def test_an_overlapping_actancy_is_refused_before_it_is_written(self):
        create_acting_assignment(
            org_unit=self.department,
            actor=self.hr,
            acting_user=self.cover,
            start_date=self.today,
            end_date=self.today + timedelta(days=7),
        )
        assignment = ActingAssignment(
            org_unit=self.department,
            acting_user=make_user("acting.second@test.luanar"),
            created_by=self.hr,
            start_date=self.today + timedelta(days=3),
            end_date=self.today + timedelta(days=9),
        )
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("start_date", caught.exception.error_dict)
        # Nothing was written: the conflict is caught before the save, so the
        # seat is never briefly double-booked.
        self.assertEqual(ActingAssignment.objects.count(), 1)

    def test_an_abutting_actancy_is_allowed(self):
        create_acting_assignment(
            org_unit=self.department,
            actor=self.hr,
            acting_user=self.cover,
            start_date=self.today,
            end_date=self.today + timedelta(days=7),
        )
        assignment = ActingAssignment(
            org_unit=self.department,
            acting_user=make_user("acting.abutting@test.luanar"),
            created_by=self.hr,
            start_date=self.today + timedelta(days=8),
        )
        assignment.full_clean()

    def test_a_different_unit_is_not_a_conflict(self):
        other_unit = OrgUnit.objects.create(
            name="Department of Physics",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )
        create_acting_assignment(
            org_unit=self.department,
            actor=self.hr,
            acting_user=self.cover,
            start_date=self.today,
        )
        assignment = ActingAssignment(
            org_unit=other_unit,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today,
        )
        assignment.full_clean()

    def test_editing_an_actancy_does_not_conflict_with_itself(self):
        existing = create_acting_assignment(
            org_unit=self.department,
            actor=self.hr,
            acting_user=self.cover,
            start_date=self.today,
            end_date=self.today + timedelta(days=7),
        )
        existing.reason = "HOD on study leave (extended)"
        existing.full_clean()
        existing.save()

    def test_a_role_actancy_and_a_person_actancy_do_not_collide(self):
        create_acting_assignment(
            org_unit=self.department,
            actor=self.hr,
            role=self.dean_role,
            start_date=self.today,
        )
        person_scoped = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today,
        )
        person_scoped.full_clean()


class ActancyWindowTests(ActingTestCase):
    def test_a_future_actancy_is_scheduled_not_active(self):
        assignment = ActingAssignment.objects.create(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today + timedelta(days=7),
        )
        self.assertEqual(assignment.state, "scheduled")
        self.assertFalse(assignment.is_active_on(self.today))

    def test_a_past_actancy_has_ended(self):
        assignment = ActingAssignment.objects.create(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today - timedelta(days=10),
            end_date=self.today - timedelta(days=1),
        )
        self.assertEqual(assignment.state, "ended")

    def test_an_open_ended_actancy_is_active_and_never_ends(self):
        assignment = ActingAssignment.objects.create(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today - timedelta(days=365),
        )
        self.assertEqual(assignment.state, "active")
        self.assertTrue(assignment.is_active_on(self.today + timedelta(days=3650)))

    def test_the_end_date_is_inclusive(self):
        end = self.today + timedelta(days=3)
        assignment = ActingAssignment.objects.create(
            org_unit=self.department,
            acting_user=self.cover,
            created_by=self.hr,
            start_date=self.today,
            end_date=end,
        )
        self.assertTrue(assignment.is_active_on(end))
        self.assertFalse(assignment.is_active_on(end + timedelta(days=1)))


class OverlapDetectionTests(ActingTestCase):
    def test_overlapping_periods_collide(self):
        first = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        second = ActingAssignment(
            org_unit=self.department,
            acting_user=self.head,
            start_date=date(2026, 3, 15),
            end_date=date(2026, 4, 15),
        )
        self.assertTrue(first.overlaps(second))
        self.assertTrue(second.overlaps(first))

    def test_abutting_periods_do_not_collide(self):
        first = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        second = ActingAssignment(
            org_unit=self.department,
            acting_user=self.head,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        self.assertFalse(first.overlaps(second))

    def test_an_open_ended_actancy_collides_with_everything_later(self):
        first = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            start_date=date(2026, 3, 1),
            end_date=None,
        )
        second = ActingAssignment(
            org_unit=self.department,
            acting_user=self.head,
            start_date=date(2030, 1, 1),
            end_date=date(2030, 2, 1),
        )
        self.assertTrue(first.overlaps(second))

    def test_a_different_unit_is_not_a_conflict(self):
        other = OrgUnit.objects.create(
            name="Department of Physics",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )
        first = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        second = ActingAssignment(
            org_unit=other,
            acting_user=self.cover,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        self.assertFalse(first.overlaps(second))

    def test_a_role_actancy_and_a_person_actancy_do_not_collide(self):
        person_seat = ActingAssignment(
            org_unit=self.department,
            acting_user=self.cover,
            role=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        role_seat = ActingAssignment(
            org_unit=self.department,
            acting_user=self.head,
            role=self.dean_role,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        self.assertFalse(person_seat.overlaps(role_seat))


class CreateActingAssignmentTests(ActingTestCase):
    def test_a_first_actancy_is_recorded(self):
        assignment = create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            reason="HOD on study leave",
        )
        self.assertIsNotNone(assignment.pk)
        self.assertEqual(assignment.reason, "HOD on study leave")

    def test_an_overlapping_actancy_is_refused_and_nothing_is_written(self):
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
        )
        with self.assertRaises(ActingAssignmentConflictError) as caught:
            create_acting_assignment(
                org_unit=self.department,
                acting_user=self.head,
                actor=self.hr,
                start_date=self.today + timedelta(days=10),
                end_date=self.today + timedelta(days=40),
            )
        self.assertEqual(ActingAssignment.objects.count(), 1)
        self.assertIn("already covers", str(caught.exception))

    def test_an_abutting_actancy_is_allowed(self):
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=7),
        )
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.head,
            actor=self.hr,
            start_date=self.today + timedelta(days=8),
            end_date=self.today + timedelta(days=20),
        )
        self.assertEqual(ActingAssignment.objects.count(), 2)

    def test_a_role_actancy_conflicts_with_another_role_actancy(self):
        create_acting_assignment(
            org_unit=self.department,
            role=self.dean_role,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=10),
        )
        with self.assertRaises(ActingAssignmentConflictError):
            create_acting_assignment(
                org_unit=self.department,
                role=self.dean_role,
                actor=self.hr,
                start_date=self.today + timedelta(days=5),
                end_date=self.today + timedelta(days=15),
            )

    def test_a_person_actancy_and_a_role_actancy_coexist(self):
        create_acting_assignment(
            org_unit=self.department,
            role=self.dean_role,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=10),
        )
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today,
            end_date=self.today + timedelta(days=10),
        )
        self.assertEqual(ActingAssignment.objects.count(), 2)

    def test_naming_neither_target_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            create_acting_assignment(
                org_unit=self.department, actor=self.hr, start_date=self.today
            )

    def test_naming_both_targets_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            create_acting_assignment(
                org_unit=self.department,
                acting_user=self.cover,
                role=self.dean_role,
                actor=self.hr,
                start_date=self.today,
            )


class CoveringLookupTests(ActingTestCase):
    def test_the_current_actancy_is_found(self):
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=1),
        )
        found = covering_acting_assignment(self.department)
        self.assertIsNotNone(found)
        self.assertEqual(found.acting_user_id, self.cover.pk)

    def test_an_actancy_outside_the_window_is_not_found(self):
        create_acting_assignment(
            org_unit=self.department,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today + timedelta(days=30),
            end_date=self.today + timedelta(days=60),
        )
        self.assertIsNone(covering_acting_assignment(self.department))

    def test_another_units_actancy_is_not_returned(self):
        other = OrgUnit.objects.create(
            name="Department of Physics",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )
        create_acting_assignment(
            org_unit=other,
            acting_user=self.cover,
            actor=self.hr,
            start_date=self.today,
        )
        self.assertIsNone(covering_acting_assignment(self.department))
