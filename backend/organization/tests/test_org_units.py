"""Tree rules for :class:`~organization.models.OrgUnit`.

The rules pinned here are the ones SQL cannot enforce, so they are exactly the
ones that need tests: which parent types are legal, that the tree has one apex,
that a unit is never its own ancestor, and that the designated approver actually
holds the role the unit escalates in. Each of those, if wrong, produces an
approval chain that silently routes to the wrong person or loops forever — the
failure mode nobody notices until somebody's leave is approved by the wrong dean.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organization.models import OrgUnit
from organization.exceptions import OrgUnitCycleError
from users.models import User
from workflows.models import ApproverRole, RoleAssignment


def make_user(username, *, role=None):
    """A plain account. The tree grants authority through role holdings, not
    through ``User.role``, so an ordinary employee account is all these tests
    need — no approver role required to *be* appointed to a unit."""
    return User.objects.create_user(
        username=username,
        email=username,
        password="testpass123",
        role=role or User.Role.EMPLOYEE,
        first_name="Tree",
        last_name="Tester",
    )


class OrgUnitTestCase(TestCase):
    """Shared tree fixture: Institution > Faculty > Department > Team."""

    def setUp(self):
        self.institution = OrgUnit.objects.create(
            name="Luanar University", unit_type=OrgUnit.UnitType.INSTITUTION
        )
        self.faculty = OrgUnit.objects.create(
            name="Faculty of Science",
            unit_type=OrgUnit.UnitType.FACULTY,
            parent=self.institution,
        )
        self.department = OrgUnit.objects.create(
            name="Department of Computer Science",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.faculty,
        )
        self.team = OrgUnit.objects.create(
            name="Software Team",
            unit_type=OrgUnit.UnitType.TEAM,
            parent=self.department,
        )


class ParentTypeMatrixTests(OrgUnitTestCase):
    def test_a_faculty_may_sit_under_the_institution(self):
        faculty = OrgUnit(
            name="Faculty of Arts",
            unit_type=OrgUnit.UnitType.FACULTY,
            parent=self.institution,
        )
        faculty.full_clean(exclude=["approver_role", "designated_approver"])
        faculty.save()

    def test_a_team_under_a_programme_is_allowed(self):
        programme = OrgUnit(
            name="Software Engineering Programme",
            unit_type=OrgUnit.UnitType.PROGRAMME,
            parent=self.department,
        )
        programme.full_clean(exclude=["approver_role", "designated_approver"])
        programme.save()
        nested = OrgUnit(
            name="Cohort 1 Team",
            unit_type=OrgUnit.UnitType.TEAM,
            parent=programme,
        )
        nested.full_clean(exclude=["approver_role", "designated_approver"])
        nested.save()

    def test_a_team_may_not_sit_under_a_faculty(self):
        team = OrgUnit(
            name="Faculty Team",
            unit_type=OrgUnit.UnitType.TEAM,
            parent=self.faculty,
        )
        with self.assertRaises(ValidationError) as caught:
            team.full_clean(exclude=["approver_role", "designated_approver"])
        self.assertIn("parent", caught.exception.error_dict)

    def test_a_faculty_may_not_sit_under_a_department(self):
        faculty = OrgUnit(
            name="Nested Faculty",
            unit_type=OrgUnit.UnitType.FACULTY,
            parent=self.department,
        )
        with self.assertRaises(ValidationError):
            faculty.full_clean(exclude=["approver_role", "designated_approver"])

    def test_an_institution_may_not_be_nested_under_another_unit(self):
        nested = OrgUnit(
            name="Satellite Campus",
            unit_type=OrgUnit.UnitType.INSTITUTION,
            parent=self.faculty,
        )
        with self.assertRaises(ValidationError) as caught:
            nested.full_clean(exclude=["approver_role", "designated_approver"])
        self.assertIn("parent", caught.exception.error_dict)

    def test_a_non_institution_must_have_a_parent(self):
        orphan = OrgUnit(name="Floating Team", unit_type=OrgUnit.UnitType.TEAM)
        with self.assertRaises(ValidationError) as caught:
            orphan.full_clean(exclude=["approver_role", "designated_approver"])
        self.assertIn("parent", caught.exception.error_dict)

    def test_the_database_refuses_a_non_institution_without_a_parent(self):
        # ``clean()`` is not called on ``save()``, so the constraint is the
        # backstop for rows written by a script or a data migration.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrgUnit.objects.create(
                    name="Orphan Team", unit_type=OrgUnit.UnitType.TEAM
                )


class SingleRootTests(OrgUnitTestCase):
    def test_a_second_apex_is_refused(self):
        rival = OrgUnit(
            name="Rival University", unit_type=OrgUnit.UnitType.INSTITUTION
        )
        with self.assertRaises(ValidationError) as caught:
            rival.full_clean(exclude=["approver_role", "designated_approver"])
        self.assertIn("parent", caught.exception.error_dict)

    def test_the_database_allows_only_one_apex(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrgUnit.objects.create(
                    name="Second Institution",
                    unit_type=OrgUnit.UnitType.INSTITUTION,
                )

    def test_saving_the_existing_apex_again_is_not_a_conflict(self):
        # An HR user editing the institution's name must not trip the rule that
        # stops a second institution being created.
        self.institution.name = "Luanar University of Namibia"
        self.institution.full_clean(exclude=["approver_role", "designated_approver"])
        self.institution.save()
        self.assertEqual(OrgUnit.objects.filter(parent__isnull=True).count(), 1)


class CycleTests(OrgUnitTestCase):
    def test_a_unit_may_not_be_moved_under_its_own_descendant(self):
        with self.assertRaises(ValidationError) as caught:
            self.faculty.parent = self.department
            self.faculty.full_clean(
                exclude=["approver_role", "designated_approver"]
            )
        self.assertIn("parent", caught.exception.error_dict)

    def test_a_unit_may_be_moved_to_a_higher_unit_that_is_not_its_descendant(self):
        self.department.parent = self.institution
        self.department.full_clean(exclude=["approver_role", "designated_approver"])
        self.department.save()
        self.assertEqual(self.department.depth(), 1)

    def test_climbing_a_stored_cycle_raises_rather_than_hanging(self):
        # Written with raw updates to reach the state ``clean()`` forbids, which
        # is what a data migration would produce if it skipped validation. The
        # two units point at each other, so the check constraint that keeps every
        # non-institution parented is still satisfied.
        OrgUnit.objects.filter(pk=self.department.pk).update(parent=self.team)
        self.team.refresh_from_db()
        self.department.refresh_from_db()

        with self.assertRaises(OrgUnitCycleError):
            list(self.team.ancestors(include_self=True))


class HierarchyHelperTests(OrgUnitTestCase):
    def test_ancestors_are_yielded_nearest_parent_first(self):
        self.assertEqual(
            [unit.pk for unit in self.team.ancestors()],
            [self.department.pk, self.faculty.pk, self.institution.pk],
        )

    def test_include_self_starts_at_the_unit_itself(self):
        chain = list(self.department.ancestors(include_self=True))
        self.assertEqual(chain[0].pk, self.department.pk)
        self.assertEqual(chain[-1].pk, self.institution.pk)

    def test_depth_counts_edges_to_the_root(self):
        self.assertEqual(self.institution.depth(), 0)
        self.assertEqual(self.faculty.depth(), 1)
        self.assertEqual(self.department.depth(), 2)
        self.assertEqual(self.team.depth(), 3)

    def test_is_within_covers_the_unit_and_its_ancestors(self):
        self.assertTrue(self.department.is_within(self.faculty))
        self.assertTrue(self.department.is_within(self.department))
        self.assertFalse(self.faculty.is_within(self.department))

    def test_a_department_under_a_faculty_is_on_the_academic_branch(self):
        self.assertTrue(self.department.is_academic_branch())

    def test_a_department_under_an_admin_department_is_not_academic(self):
        admin = OrgUnit.objects.create(
            name="Department of Human Resources",
            unit_type=OrgUnit.UnitType.ADMIN_DEPARTMENT,
            parent=self.faculty,
        )
        admin_team = OrgUnit.objects.create(
            name="HR Leave Team",
            unit_type=OrgUnit.UnitType.TEAM,
            parent=admin,
        )
        self.assertFalse(admin.is_academic_branch())
        self.assertFalse(admin_team.is_academic_branch())

    def test_the_institution_itself_is_not_an_admin_department(self):
        self.assertTrue(self.institution.is_academic_branch())


class DesignatedApproverQualificationTests(OrgUnitTestCase):
    def setUp(self):
        super().setUp()
        self.hod_role = ApproverRole.objects.create(
            code="tree_hod", label="Head of Department"
        )
        self.head = make_user("tree.head@test.luanar")

    def _hold_at(self, unit, *, institution_wide=False):
        RoleAssignment.objects.create(
            user=self.head,
            role=self.hod_role,
            org_unit=None if institution_wide else unit,
        )

    def test_a_designated_approver_holding_the_role_at_that_unit_is_accepted(self):
        self._hold_at(self.department)
        self.department.approver_role = self.hod_role
        self.department.designated_approver = self.head
        self.department.full_clean()
        self.department.save()
        self.assertTrue(self.department.designated_approver_holds_role())

    def test_a_holder_from_an_ancestor_unit_is_accepted(self):
        # A dean who also heads the department is qualified for the department.
        self._hold_at(self.faculty)
        self.department.approver_role = self.hod_role
        self.department.designated_approver = self.head
        self.department.full_clean()
        self.department.save()
        self.assertTrue(self.department.designated_approver_holds_role())

    def test_an_institution_wide_holding_is_accepted(self):
        self._hold_at(self.department, institution_wide=True)
        self.department.approver_role = self.hod_role
        self.department.designated_approver = self.head
        self.department.full_clean()
        self.department.save()
        self.assertTrue(self.department.designated_approver_holds_role())

    def test_an_unqualified_designated_approver_is_refused(self):
        self.department.approver_role = self.hod_role
        self.department.designated_approver = self.head
        with self.assertRaises(ValidationError) as caught:
            self.department.full_clean()
        self.assertIn("designated_approver", caught.exception.error_dict)
        self.assertIn(
            "does not hold",
            str(caught.exception.error_dict["designated_approver"][0]),
        )

    def test_a_holding_at_an_unrelated_unit_does_not_qualify(self):
        sibling = OrgUnit.objects.create(
            name="Department of Physics",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.faculty,
        )
        self._hold_at(sibling)
        self.department.approver_role = self.hod_role
        self.department.designated_approver = self.head
        with self.assertRaises(ValidationError):
            self.department.full_clean()

    def test_a_unit_under_construction_needs_neither_field(self):
        # Role without a person, or a person without a role, is a half-finished
        # unit. The resolver refuses to route through it; ``clean()`` must not
        # refuse to save it, or HR could never stage the work.
        self.department.approver_role = self.hod_role
        self.department.designated_approver = None
        self.department.full_clean()
        self.department.save()
        self.assertFalse(self.department.designated_approver_holds_role())


class InactiveUnitTests(OrgUnitTestCase):
    def test_a_retired_unit_stays_climbable_for_history(self):
        self.department.is_active = False
        self.department.save()
        self.assertIn(
            self.department.pk,
            [unit.pk for unit in self.team.ancestors(include_self=True)],
        )
