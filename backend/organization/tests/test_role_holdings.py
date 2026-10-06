"""Role holdings at a unit, and the institution-wide fallback that must ignore them.

A role can now be held **at a unit** as well as institution-wide, which is what
makes "this person is the Head of *that* department" expressible. The
consequence that has to be pinned here is that the two scopes are not
interchangeable: a unit-scoped holder is qualified for their own unit and
qualified for nothing else, so the institution-wide fallback used to resolve a
vacant step must not pick them up.

Getting that wrong is quiet. Nothing raises — a section simply routes to somebody
whose authority stops at one department, and the application is approved by a
person who had no business seeing it.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organization.models import OrgUnit
from users.models import User
from workflows.models import ApproverRole, RoleAssignment, Section, Workflow
from workflows.providers import _institution_wide_holder_ids
from workflows.services import is_approver_user


def make_user(username, *, role=None):
    return User.objects.create_user(
        username=username,
        email=username,
        password="testpass123",
        role=role or User.Role.EMPLOYEE,
        first_name="Role",
        last_name="Holder",
    )


class RoleHoldingTestCase(TestCase):
    def setUp(self):
        self.institution = OrgUnit.objects.create(
            name="Luanar University", unit_type=OrgUnit.UnitType.INSTITUTION
        )
        self.science = OrgUnit.objects.create(
            name="Department of Computer Science",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )
        self.physics = OrgUnit.objects.create(
            name="Department of Physics",
            unit_type=OrgUnit.UnitType.DEPARTMENT,
            parent=self.institution,
        )

        self.hod_role = ApproverRole.objects.create(
            code="hod_test", label="Head of Department", is_institution_wide=False
        )
        self.registrar_role = ApproverRole.objects.create(
            code="registrar_test",
            label="Registrar",
            is_institution_wide=True,
        )
        self.head = make_user("holding.head@test.luanar")
        self.registrar = make_user("holding.registrar@test.luanar")


class ScopeValidationTests(RoleHoldingTestCase):
    def test_a_unit_scoped_holding_of_a_team_role_is_accepted(self):
        assignment = RoleAssignment(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        assignment.full_clean()
        assignment.save()
        self.assertFalse(assignment.is_institution_wide)
        self.assertIn("Computer Science", str(assignment))

    def test_an_institution_wide_holding_of_an_institution_wide_role_is_accepted(self):
        assignment = RoleAssignment(user=self.registrar, role=self.registrar_role)
        assignment.full_clean()
        assignment.save()
        self.assertTrue(assignment.is_institution_wide)

    def test_a_scoped_holding_of_a_team_role_with_no_unit_is_still_refused(self):
        # The pre-existing rule, unchanged: a team role held nowhere is a role
        # nobody has, and letting the row exist would let the tree fall back to
        # it without anybody having decided that was a good idea.
        assignment = RoleAssignment(user=self.head, role=self.hod_role)
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("org_unit", caught.exception.error_dict)


class UniquenessTests(RoleHoldingTestCase):
    def test_one_person_may_hold_a_role_at_two_different_units(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.physics
        )
        self.assertEqual(RoleAssignment.objects.filter(user=self.head).count(), 2)

    def test_the_same_role_at_the_same_unit_twice_is_refused(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoleAssignment.objects.create(
                    user=self.head, role=self.hod_role, org_unit=self.science
                )

    def test_a_unit_holding_and_an_institution_wide_holding_can_coexist(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.registrar_role, org_unit=self.science
        )
        RoleAssignment.objects.create(
            user=self.head, role=self.registrar_role, org_unit=None
        )
        self.assertEqual(RoleAssignment.objects.filter(user=self.head).count(), 2)

    def test_the_same_institution_wide_holding_twice_is_refused(self):
        """The scoping must widen holdings, not weaken uniqueness within one.

        An institution-wide holding stores ``org_unit_id`` as NULL, and
        PostgreSQL counts NULLs as distinct inside a unique index. Relying on
        the default would quietly reinstate what the pre-tree
        ``(user, role)`` constraint used to forbid, and nothing would raise:
        the tree would just find two holders for one institution-wide seat.
        """
        RoleAssignment.objects.create(
            user=self.registrar, role=self.registrar_role, org_unit=None
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoleAssignment.objects.create(
                    user=self.registrar, role=self.registrar_role, org_unit=None
                )


class InstitutionWideFallbackTests(RoleHoldingTestCase):
    def test_a_unit_scoped_holder_is_not_an_institution_wide_fallback(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        self.assertEqual(_institution_wide_holder_ids(self.hod_role), [])

    def test_an_institution_wide_holder_still_resolves(self):
        RoleAssignment.objects.create(
            user=self.registrar, role=self.registrar_role, org_unit=None
        )
        self.assertEqual(
            _institution_wide_holder_ids(self.registrar_role),
            [self.registrar.pk],
        )

    def test_a_mixed_set_returns_only_the_institution_wide_holder(self):
        other = make_user("holding.mixed@test.luanar")
        RoleAssignment.objects.create(
            user=other, role=self.registrar_role, org_unit=self.physics
        )
        RoleAssignment.objects.create(
            user=self.registrar, role=self.registrar_role, org_unit=None
        )
        self.assertEqual(
            _institution_wide_holder_ids(self.registrar_role),
            [self.registrar.pk],
        )

    def test_an_inactive_user_is_not_a_fallback(self):
        self.registrar.is_active = False
        self.registrar.save()
        RoleAssignment.objects.create(
            user=self.registrar, role=self.registrar_role, org_unit=None
        )
        self.assertEqual(_institution_wide_holder_ids(self.registrar_role), [])

    def test_a_vacant_institution_wide_step_ignores_a_unit_scoped_holder(self):
        """The end-to-end consequence, at the level a reader cares about.

        A section routed to an institution-wide role with nobody institution-wide
        holding it must still be refused. Picking the department's head instead
        would approve the application and hand it to somebody whose authority
        stops at one department.
        """
        section_role = ApproverRole.objects.create(
            code="vacant_iw", label="Vacant Institution-Wide Role",
            is_institution_wide=True,
        )
        RoleAssignment.objects.create(
            user=self.head, role=section_role, org_unit=self.science
        )
        workflow = Workflow.objects.create(name="IW workflow")
        section = Section.objects.create(
            workflow=workflow,
            name="Final step",
            order=1,
            approver_role=section_role,
        )
        self.assertEqual(_institution_wide_holder_ids(section_role), [])

        from workflows.providers import WorkflowConfigError, resolve_section_approvers

        with self.assertRaises(WorkflowConfigError) as caught:
            resolve_section_approvers(section)
        self.assertIn("no active holder", str(caught.exception))


class ApproverStatusTests(RoleHoldingTestCase):
    def test_a_unit_scoped_holder_counts_as_an_approver(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        self.assertTrue(is_approver_user(self.head))

    def test_somebody_with_no_holding_is_not_an_approver(self):
        self.assertFalse(is_approver_user(self.head))

    def test_a_deactivated_role_retires_the_approver_status(self):
        RoleAssignment.objects.create(
            user=self.head, role=self.hod_role, org_unit=self.science
        )
        self.hod_role.is_active = False
        self.hod_role.save()
        self.assertFalse(is_approver_user(self.head))
