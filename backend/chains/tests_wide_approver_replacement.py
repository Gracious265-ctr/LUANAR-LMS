"""Replacing a wide approver carries their positions to the successor.

A wide approver (institution-, team-, or campus-wide) staffs chains from a single
holding: the steps that name their role and point at them, and the chains they
sit on as a normal member. When HR hands that holding to somebody else, the
successor must inherit those positions rather than leaving every step and
membership pointing at a person who no longer holds the role.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from organisation.models import ApproverRole, RoleAssignment
from organisation.services import (
    RoleActionError,
    create_campus_role_assignment,
    create_team_role_assignment,
    replace_role_assignment,
)
from workflows.models import SectionMember, WorkflowMember

from .testing import (
    DEV_PASSWORD,
    campus_for,
    ensure_roles,
    make_approver,
    make_employee,
    make_team,
)

User = get_user_model()


class WideApproverReplacementBase(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username="hr@wide.test",
            email="hr@wide.test",
            password=DEV_PASSWORD,
            first_name="Hana",
            role=User.Role.HR,
        )

    def staff_section(self, section, user):
        """Point ``section`` at ``user`` and record the open period."""
        section.approver = user
        section.save(update_fields=["approver"])
        SectionMember.objects.create(
            section=section, user=user, effective_from=timezone.localdate()
        )

    def open_period_exists(self, section, user):
        return SectionMember.objects.filter(
            section=section, user=user, effective_to__isnull=True
        ).exists()


class TeamWideReplacementTests(WideApproverReplacementBase):
    def setUp(self):
        super().setUp()
        # A team-wide role: held on the team, not institution-wide, so the role
        # is written at a team scope.
        self.role = ensure_roles("supervisor")["supervisor"]
        self.team = make_team("Wide Team", ("supervisor",))
        self.workflow = self.team.workflows.first()
        self.section = self.workflow.sections.get(order=1)
        self.old = make_approver(
            "supervisor",
            username="old-team@wide.test",
            institution_wide=False,
            team=self.team,
        )
        self.new = make_approver(
            "supervisor",
            username="new-team@wide.test",
            institution_wide=False,
            team=self.team,
        )

    def replace(self, user):
        return create_team_role_assignment(
            team=self.team, role=self.role, user=user, actor=self.hr
        )

    def test_repointing_the_holding_moves_the_step(self):
        self.staff_section(self.section, self.old)
        self.replace(self.old)
        self.replace(self.new)

        self.section.refresh_from_db()
        self.assertEqual(self.section.approver_id, self.new.pk)
        self.assertFalse(self.open_period_exists(self.section, self.old))
        self.assertTrue(self.open_period_exists(self.section, self.new))

    def test_a_step_pointed_somewhere_else_is_left_alone(self):
        other = make_approver(
            "supervisor",
            username="other-team@wide.test",
            institution_wide=False,
            team=self.team,
        )
        self.staff_section(self.section, other)
        self.replace(self.old)
        self.replace(self.new)
        self.section.refresh_from_db()
        self.assertEqual(self.section.approver_id, other.pk)

    def test_a_wide_membership_moves_to_the_successor(self):
        member = WorkflowMember.objects.create(
            workflow=self.workflow,
            user=self.old,
            team=self.team,
            is_wide_approver=True,
        )
        self.replace(self.old)
        self.replace(self.new)
        member.refresh_from_db()
        self.assertEqual(member.user_id, self.new.pk)


class CampusWideReplacementTests(WideApproverReplacementBase):
    def setUp(self):
        super().setUp()
        # A campus-wide role must be held at a scope, not institution-wide.
        self.role = ensure_roles("campus_registrar")["campus_registrar"]
        self.role.is_institution_wide = False
        self.role.save(update_fields=["is_institution_wide"])
        self.campus = campus_for("Wide Campus")
        self.team = make_team(
            "Campus Wide Team", ("campus_registrar",), campus="Wide Campus"
        )
        self.workflow = self.team.workflows.first()
        self.section = self.workflow.sections.get(order=1)
        self.old = make_approver(
            "campus_registrar",
            username="old-campus@wide.test",
            institution_wide=False,
            category="academic",
        )
        self.new = make_approver(
            "campus_registrar",
            username="new-campus@wide.test",
            institution_wide=False,
            category="academic",
        )

    def replace(self, user):
        return create_campus_role_assignment(
            campus=self.campus, role=self.role, user=user, actor=self.hr
        )

    def test_repointing_the_holding_moves_the_step(self):
        self.staff_section(self.section, self.old)
        self.replace(self.old)
        self.replace(self.new)
        self.section.refresh_from_db()
        self.assertEqual(self.section.approver_id, self.new.pk)

    def test_a_team_at_another_campus_is_left_alone(self):
        other_team = make_team(
            "Other Campus Team", ("campus_registrar",), campus="Other Campus"
        )
        other_section = other_team.workflows.first().sections.get(order=1)
        self.staff_section(other_section, self.old)
        self.replace(self.old)
        self.replace(self.new)
        other_section.refresh_from_db()
        self.assertEqual(other_section.approver_id, self.old.pk)


class InstitutionWideReplacementTests(WideApproverReplacementBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()  # type: ignore[assignment]
        self.client.force_authenticate(self.hr)
        self.role = ensure_roles("registrar")["registrar"]
        self.role.is_institution_wide = True
        self.role.save(update_fields=["is_institution_wide"])
        # Two teams: an institution-wide holding reaches them both.
        self.team_a = make_team("Institution Team A", ("registrar",))
        self.team_b = make_team("Institution Team B", ("registrar",))
        self.section_a = self.team_a.workflows.first().sections.get(order=1)
        self.section_b = self.team_b.workflows.first().sections.get(order=1)
        self.old = make_approver(
            "registrar", username="old-inst@wide.test", institution_wide=False
        )
        self.new = make_approver(
            "registrar", username="new-inst@wide.test", institution_wide=False
        )

    def holding_for(self, user):
        RoleAssignment.objects.filter(role=self.role).delete()
        return RoleAssignment.objects.create(user=user, role=self.role)

    def test_service_moves_every_step_the_holder_staffed(self):
        holder = self.holding_for(self.old)
        for section in (self.section_a, self.section_b):
            self.staff_section(section, self.old)

        replace_role_assignment(assignment=holder, user=self.new, actor=self.hr)

        self.section_a.refresh_from_db()
        self.section_b.refresh_from_db()
        self.assertEqual(self.section_a.approver_id, self.new.pk)
        self.assertEqual(self.section_b.approver_id, self.new.pk)

    def test_replacing_with_the_current_holder_is_refused(self):
        holder = self.holding_for(self.old)
        with self.assertRaises(RoleActionError):
            replace_role_assignment(assignment=holder, user=self.old, actor=self.hr)

    def test_replace_endpoint_hands_over_the_holding(self):
        holder = self.holding_for(self.old)
        self.staff_section(self.section_a, self.old)

        response = self.client.post(
            f"/api/v1/role-assignments/{holder.pk}/replace/",
            {"user": self.new.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        holder.refresh_from_db()
        self.assertEqual(holder.user_id, self.new.pk)
        self.section_a.refresh_from_db()
        self.assertEqual(self.section_a.approver_id, self.new.pk)

    def test_replace_endpoint_is_hr_only(self):
        holder = self.holding_for(self.old)
        employee = make_employee("plain@wide.test")
        self.client.force_authenticate(employee)
        response = self.client.post(
            f"/api/v1/role-assignments/{holder.pk}/replace/",
            {"user": self.new.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
