"""The fixture organisation provider returns consistent, well-shaped data.

The seed data is a placeholder, but the *contract* is not: every method must
return records whose fields are populated and whose cross-references
(employees -> grades and home units, role holders -> units and employees,
units -> parents) actually resolve inside the same dataset.
"""

from django.test import SimpleTestCase

from directory.factory import get_organization_provider
from directory.provider import EmployeeRecord, GradeRecord, OrgUnitRecord, RoleHolder

BRANCHES = {"academic", "administrative"}
GENDERS = {"male", "female"}
UNIT_TYPES = {
    "institution",
    "campus",
    "faculty",
    "department_academic",
    "department_admin",
    "team",
}
ROLES = {
    "hod",
    "dean",
    "manager",
    "supervisor",
    "campus_registrar",
    "institutional_registrar",
}


class FixtureProviderContractTests(SimpleTestCase):
    """Shape and cross-reference consistency of every provider method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = get_organization_provider()

    def test_every_method_returns_the_declared_record_types(self):
        for employee in self.provider.get_employees():
            with self.subTest(employee=employee.id):
                self.assertIsInstance(employee, EmployeeRecord)
        for grade in self.provider.get_grades():
            with self.subTest(grade=grade.id):
                self.assertIsInstance(grade, GradeRecord)
        for unit in self.provider.get_org_units():
            with self.subTest(unit=unit.id):
                self.assertIsInstance(unit, OrgUnitRecord)
        for holder in self.provider.get_role_holders():
            with self.subTest(holder=(holder.org_unit_id, holder.role)):
                self.assertIsInstance(holder, RoleHolder)

    def test_employees_have_populated_fields(self):
        employees = self.provider.get_employees()
        self.assertGreater(len(employees), 0)
        for employee in employees:
            with self.subTest(employee=employee.id):
                self.assertTrue(employee.id)
                self.assertTrue(employee.name)
                self.assertIn("@", employee.email)
                self.assertIn(employee.branch, BRANCHES)
                self.assertIn(employee.gender, GENDERS)

    def test_employee_point_lookups_round_trip(self):
        for employee in self.provider.get_employees():
            with self.subTest(employee=employee.id):
                self.assertEqual(
                    self.provider.get_employee(employee.id), employee
                )
        self.assertIsNone(self.provider.get_employee("does-not-exist"))

    def test_employee_grade_ids_exist_in_the_grade_registry(self):
        grade_ids = {grade.id for grade in self.provider.get_grades()}
        for employee in self.provider.get_employees():
            with self.subTest(employee=employee.id):
                self.assertIn(employee.grade_id, grade_ids)

    def test_employee_home_units_exist_in_the_org_tree(self):
        unit_ids = {unit.id for unit in self.provider.get_org_units()}
        for employee in self.provider.get_employees():
            with self.subTest(employee=employee.id):
                if employee.home_unit_id is not None:
                    self.assertIn(employee.home_unit_id, unit_ids)

    def test_branch_filter_narrows_the_result(self):
        academic = self.provider.get_employees(branch="academic")
        administrative = self.provider.get_employees(branch="administrative")
        self.assertGreater(len(academic), 0)
        self.assertGreater(len(administrative), 0)
        for employee in academic:
            self.assertEqual(employee.branch, "academic")
        for employee in administrative:
            self.assertEqual(employee.branch, "administrative")

    def test_home_unit_filter_narrows_the_result(self):
        unit_ids = {unit.id for unit in self.provider.get_org_units()}
        for unit_id in unit_ids:
            with self.subTest(unit=unit_id):
                for employee in self.provider.get_employees(home_unit_id=unit_id):
                    self.assertEqual(employee.home_unit_id, unit_id)

    def test_grades_have_populated_fields_and_round_trip(self):
        grades = self.provider.get_grades()
        self.assertGreater(len(grades), 0)
        for grade in grades:
            with self.subTest(grade=grade.id):
                self.assertTrue(grade.id)
                self.assertTrue(grade.name)
                self.assertEqual(self.provider.get_grade(grade.id), grade)
        self.assertIsNone(self.provider.get_grade("does-not-exist"))

    def test_org_units_are_well_formed_and_parents_resolve(self):
        units = self.provider.get_org_units()
        self.assertGreater(len(units), 0)
        unit_ids = {unit.id for unit in units}
        institutions = [unit for unit in units if unit.unit_type == "institution"]
        self.assertEqual(len(institutions), 1)
        for unit in units:
            with self.subTest(unit=unit.id):
                self.assertTrue(unit.id)
                self.assertTrue(unit.name)
                self.assertIn(unit.unit_type, UNIT_TYPES)
                if unit.parent_id is not None:
                    self.assertIn(unit.parent_id, unit_ids)

    def test_org_units_cover_the_shapes_the_sync_exercises(self):
        types = {unit.unit_type for unit in self.provider.get_org_units()}
        for expected in (
            "institution",
            "campus",
            "faculty",
            "department_academic",
            "department_admin",
        ):
            self.assertIn(expected, types)
        self.assertTrue(any(unit.has_teams for unit in self.provider.get_org_units()))
        self.assertTrue(
            any(not unit.has_teams for unit in self.provider.get_org_units()
                if unit.unit_type == "department_admin")
        )

    def test_role_holders_reference_known_units_roles_and_employees(self):
        holders = self.provider.get_role_holders()
        self.assertGreater(len(holders), 0)
        unit_ids = {unit.id for unit in self.provider.get_org_units()}
        for holder in holders:
            with self.subTest(holder=(holder.org_unit_id, holder.role)):
                self.assertIn(holder.org_unit_id, unit_ids)
                self.assertIn(holder.role, ROLES)
                if holder.employee_id is not None:
                    self.assertIsNotNone(
                        self.provider.get_employee(holder.employee_id)
                    )

    def test_at_least_one_role_holder_is_vacant(self):
        vacant = [
            holder for holder in self.provider.get_role_holders()
            if holder.employee_id is None
        ]
        self.assertGreater(len(vacant), 0)
