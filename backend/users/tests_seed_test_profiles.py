"""The end-to-end test-profile seed, and the routing it claims to establish.

``seed_test_profiles`` is a fixture command, and a fixture command is only
useful if what it builds actually routes. These tests therefore assert the two
things that would make it silently useless: that every account can sign in, and
that each team's chain passes the same readiness check HR's screens run — which
is what would catch the seed writing a step nobody can act on.
"""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import TestCase

from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment
from teams.models import Team, TeamRoleAssignment
from users.management.commands.seed_test_profiles import (
    ACCOUNT_DOMAIN,
    DEV_PASSWORD,
    EMPLOYEE_ACCOUNTS,
    ROLE_ACCOUNTS,
)
from chains.services import validate_team

User = get_user_model()


class SeedTestProfilesCommandTests(TestCase):
    def setUp(self):
        self.out = StringIO()
        call_command("seed_test_profiles", stdout=self.out)

    def _email(self, local: str) -> str:
        return f"{local}@{ACCOUNT_DOMAIN}"

    def test_every_seeded_account_can_sign_in(self):
        locals_ = [spec["username"] for spec in ROLE_ACCOUNTS]
        locals_ += [local for local, *_ in EMPLOYEE_ACCOUNTS]

        self.assertEqual(len(locals_), 14)
        for local in locals_:
            email = self._email(local)
            self.assertIsNotNone(
                authenticate(username=email, password=DEV_PASSWORD),
                f"{email} cannot sign in",
            )

    def test_hr_account_carries_the_hr_role(self):
        hr = User.objects.get(username=self._email("hr"))
        self.assertEqual(hr.role, User.Role.HR)

    def test_both_teams_are_ready_to_route(self):
        for code in ("registry-operations", "main-campus-academic"):
            team = Team.objects.get(code=code)
            readiness = validate_team(team)
            self.assertEqual(
                readiness.issues,
                (),
                f"{team.name} is not ready: "
                f"{[issue.message for issue in readiness.issues]}",
            )

    def test_registrar_and_dvc_are_held_institution_wide(self):
        for code in ("registrar", "dvc"):
            role = ApproverRole.objects.get(code=code)
            self.assertTrue(role.is_institution_wide)
            holder = RoleAssignment.objects.get(role=role)
            self.assertEqual(holder.user.username, self._email(code))

    def test_campus_registrar_is_not_institution_wide(self):
        # It must be a campus-wide office, not an institution-wide one: an
        # institution-wide approver may not serve an academic team, so modelling
        # it that way would leave the campus chain unroutable.
        role = ApproverRole.objects.get(code="campus_registrar")
        self.assertFalse(role.is_institution_wide)
        holder = CampusRoleAssignment.objects.get(role=role)
        self.assertEqual(holder.user.username, self._email("campus-registrar"))
        self.assertEqual(holder.campus.code, "main-campus")

    def test_the_academic_team_sits_at_the_seeded_campus(self):
        team = Team.objects.get(code="main-campus-academic")
        self.assertEqual(team.category, Team.Category.ACADEMIC)
        self.assertEqual(team.campus, Campus.objects.get(code="main-campus"))

    def test_employees_are_on_the_team_their_chain_belongs_to(self):
        for local, _first, _last, team_key in EMPLOYEE_ACCOUNTS:
            profile = User.objects.get(username=self._email(local)).employee_profile
            self.assertIsNotNone(profile.team)
            expected = (
                "registry-operations"
                if team_key == "admin"
                else "main-campus-academic"
            )
            self.assertEqual(profile.team.code, expected)

    def test_it_is_idempotent(self):
        call_command("seed_test_profiles", stdout=StringIO())

        self.assertEqual(
            User.objects.filter(email__iendswith=f"@{ACCOUNT_DOMAIN}").count(), 14
        )
        for code in ("registry-operations", "main-campus-academic"):
            self.assertEqual(validate_team(Team.objects.get(code=code)).issues, ())

    def test_a_registrar_holding_from_elsewhere_is_taken_over(self):
        """A second registrar office cannot be created, so the holding moves."""
        role = ApproverRole.objects.get(code="registrar")
        existing = RoleAssignment.objects.get(role=role)

        other = User.objects.create_user(
            username="old.registrar@luanar.ac.mw",
            email="old.registrar@luanar.ac.mw",
            password=DEV_PASSWORD,
        )
        existing.user = other
        existing.save(update_fields=["user"])

        call_command("seed_test_profiles", stdout=StringIO())

        holders = list(RoleAssignment.objects.filter(role=role))
        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0].user.username, self._email("registrar"))

        # The step that named the previous holder is re-pointed, so the chain
        # does not report as broken after the take-over.
        team = Team.objects.get(code="registry-operations")
        self.assertEqual(validate_team(team).issues, ())

    def test_the_administration_team_has_a_designated_manager(self):
        """The manager capacity is seeded, so the Teams-app manager path is testable."""
        team = Team.objects.get(code="registry-operations")
        managers = TeamRoleAssignment.objects.filter(
            team=team, is_team_manager=True
        )
        self.assertEqual(managers.count(), 1)
        manager = managers.get()
        self.assertEqual(manager.user.username, self._email("hod"))
        self.assertEqual(manager.role.code, "hod")
        # A manager holds a *team*-wide role: an institution-wide one belongs
        # under Approvers and carries no manager flag.
        self.assertFalse(manager.role.is_institution_wide)

    def test_the_manager_designation_survives_a_re_run(self):
        call_command("seed_test_profiles", stdout=StringIO())
        team = Team.objects.get(code="registry-operations")
        self.assertEqual(
            TeamRoleAssignment.objects.filter(
                team=team, is_team_manager=True
            ).count(),
            1,
        )
