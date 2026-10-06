"""Resolving where an employee sits in the tree.

The point of deriving the home unit rather than storing it is that it can never
disagree with the team and department that ``EmployeeProfile`` already holds.
These tests pin the precedence that makes that true, and the two ways an employee
can end up with no unit at all — both of which are ordinary states during a
migration rather than errors.
"""

from django.test import TestCase

from organization.exceptions import NoHomeUnitError
from organization.models import OrgUnit
from organization.services import (
    require_home_unit,
    resolve_home_unit,
    unit_chain_to_root,
)
from users.models import Department, EmployeeProfile, User
from workflows.models import Team


def make_user(username, **kwargs):
    return User.objects.create_user(
        username=username,
        email=username,
        password="testpass123",
        first_name="Home",
        last_name="Tester",
        **kwargs,
    )


class HomeUnitTestCase(TestCase):
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
        self.team_unit = OrgUnit.objects.create(
            name="Software Team",
            unit_type=OrgUnit.UnitType.TEAM,
            parent=self.department,
        )

        self.department_row = Department.objects.create(
            name="Computer Science", org_unit=self.department
        )
        self.team_row = Team.objects.create(
            name="Software", department=self.department_row, org_unit=self.team_unit
        )

        self.employee = make_user("home.employee@test.luanar")
        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            department=self.department_row,
            team=self.team_row,
        )


class ResolveHomeUnitTests(HomeUnitTestCase):
    def test_a_bound_team_is_the_home_unit(self):
        self.assertEqual(resolve_home_unit(self.employee), self.team_unit)

    def test_the_team_wins_over_the_department(self):
        # Both are bound, and they are different units. A team is the finer
        # unit, so approvals must start there rather than at the department.
        self.assertNotEqual(self.team_unit, self.department)
        self.assertEqual(resolve_home_unit(self.employee).pk, self.team_unit.pk)

    def test_an_employee_with_no_team_falls_back_to_the_department(self):
        self.profile.team = None
        self.profile.save()
        self.assertEqual(resolve_home_unit(self.employee), self.department)

    def test_an_unbound_team_falls_back_to_a_bound_department(self):
        self.team_row.org_unit = None
        self.team_row.save()
        self.assertEqual(resolve_home_unit(self.employee), self.department)

    def test_an_employee_on_no_unit_at_all_resolves_to_none(self):
        # The state every employee is in before HR has migrated their team.
        self.team_row.org_unit = None
        self.team_row.save()
        self.department_row.org_unit = None
        self.department_row.save()
        self.assertIsNone(resolve_home_unit(self.employee))

    def test_an_employee_with_no_profile_resolves_to_none(self):
        orphan = make_user("home.noprofile@test.luanar")
        self.assertIsNone(resolve_home_unit(orphan))


class RequireHomeUnitTests(HomeUnitTestCase):
    def test_a_bound_employee_gets_their_unit(self):
        self.assertEqual(require_home_unit(self.employee), self.team_unit)

    def test_an_unmigrated_employee_is_refused_with_an_actionable_message(self):
        self.team_row.org_unit = None
        self.team_row.save()
        self.department_row.org_unit = None
        self.department_row.save()
        with self.assertRaises(NoHomeUnitError) as caught:
            require_home_unit(self.employee)
        message = str(caught.exception)
        self.assertIn("organizational tree", message)
        self.assertIn("team or department", message)


class MovingAHomeUnitTests(HomeUnitTestCase):
    def test_changing_team_moves_the_home_unit_with_it(self):
        """The reason the home unit is derived rather than stored.

        A promotion or a transfer changes one row on ``EmployeeProfile``, and the
        escalation path follows immediately. A cached ``home_unit`` column would
        still be pointing at the old department until somebody remembered to
        refresh it.
        """
        other_faculty = OrgUnit.objects.create(
            name="Faculty of Humanities",
            unit_type=OrgUnit.UnitType.FACULTY,
            parent=self.institution,
        )
        other_department_unit = OrgUnit.objects.create(
            name="Department of History",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=other_faculty,
        )
        other_department = Department.objects.create(
            name="History", org_unit=other_department_unit
        )

        self.profile.department = other_department
        self.profile.team = None
        self.profile.save()

        self.assertEqual(
            resolve_home_unit(self.employee), other_department_unit
        )
        self.assertEqual(
            [unit.pk for unit in unit_chain_to_root(other_department_unit)],
            [other_department_unit.pk, other_faculty.pk, self.institution.pk],
        )


class UnitChainTests(HomeUnitTestCase):
    def test_the_chain_runs_from_the_home_unit_up_to_the_apex(self):
        chain = unit_chain_to_root(self.team_unit)
        self.assertEqual(
            [unit.pk for unit in chain],
            [
                self.team_unit.pk,
                self.department.pk,
                self.faculty.pk,
                self.institution.pk,
            ],
        )

    def test_a_retired_unit_stays_in_the_chain_for_history(self):
        self.department.is_active = False
        self.department.save()
        chain = unit_chain_to_root(self.team_unit)
        self.assertIn(self.department.pk, [unit.pk for unit in chain])
