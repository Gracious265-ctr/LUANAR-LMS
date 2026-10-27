"""Wide-approver scope, the manager's own chain, and skip-forward routing.

Three rules meet here, and each is tested at the layer that owns it:

* **Scope.** A campus-wide holding reaches only the academic teams at its own
  campus; an institution-wide holding reaches only administration teams. The
  same scope is applied by the service that defines a wide approver
  (:func:`roles.services.wide_approver_ids_for_team`), by the approver picker,
  and by the routing provider, so the tests pin the shared function plus the
  two read surfaces that must agree with it.
* **The manager's own chain.** A designated manager is a team-wide holder, but
  they are *not* a wide approver: their own leave has to route through the team
  they run, which takes a roster row. Once they join one of the team's chains
  they are an ordinary member of one chain, and the other chains' lists stop
  offering them.
* **Forward routing.** An applicant who holds more than one stage — by
  appointment *and* by a wide role — is skipped past the **highest** stage they
  hold, never routed backwards and never asked to approve themselves.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from campuses.models import Campus, CampusRoleAssignment
from leave.models import LeaveApplication
from roles.models import ApproverRole, RoleAssignment
from roles.services import wide_approver_ids_for_team
from teams.models import Team, TeamRoleAssignment
from users.models import EmployeeProfile
from chains.models import WorkflowMember

from .providers import DatabaseWorkflowProvider
from .testing import (
    DEV_PASSWORD,
    appoint_approver_to_section,
    ensure_roles,
    grant_approver_role,
    make_employee,
    make_team,
    make_workflow,
)

User = get_user_model()

TEAMS_URL = "/api/v1/teams/"
WORKFLOWS_URL = "/api/v1/workflows/"


class WideApproverScopeTests(TestCase):
    """``wide_approver_ids_for_team`` is the one definition of a wide approver."""

    def setUp(self):
        self.roles = ensure_roles("supervisor", "hod", "registrar")
        self.campus_a = Campus.objects.create(name="Campus A", code="campus-a")
        self.campus_b = Campus.objects.create(name="Campus B", code="campus-b")

    def academic_team(self, name, campus):
        return make_team(name, ("supervisor",), campus=campus.name)

    def administration_team(self, name="Central Administration"):
        return make_team(name, ("supervisor",))

    def test_a_campus_holder_reaches_only_academic_teams_at_that_campus(self):
        holder = make_employee(
            "campus-a-holder@scope.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        CampusRoleAssignment.objects.create(
            campus=self.campus_a, role=self.roles["supervisor"], user=holder
        )
        here = self.academic_team("Campus A Faculty", self.campus_a)
        elsewhere = self.academic_team("Campus B Faculty", self.campus_b)
        admin = self.administration_team()

        self.assertIn(holder.pk, wide_approver_ids_for_team(here))
        self.assertNotIn(holder.pk, wide_approver_ids_for_team(elsewhere))
        self.assertNotIn(holder.pk, wide_approver_ids_for_team(admin))

    def test_an_institution_holder_reaches_only_administration_teams(self):
        holder = make_employee("registrar@scope.test")
        grant_approver_role(holder, "registrar", institution_wide=True)
        admin = self.administration_team()
        academic = self.academic_team("Campus A Faculty", self.campus_a)

        self.assertIn(holder.pk, wide_approver_ids_for_team(admin))
        self.assertNotIn(holder.pk, wide_approver_ids_for_team(academic))

    def test_the_designated_manager_is_not_a_wide_approver_on_their_team(self):
        team = self.administration_team()
        manager = make_employee("manager@scope.test")
        other = make_employee("other-holder@scope.test")
        TeamRoleAssignment.objects.create(
            team=team,
            role=self.roles["supervisor"],
            user=manager,
            is_team_manager=True,
        )
        TeamRoleAssignment.objects.create(
            team=team, role=self.roles["hod"], user=other
        )

        ids = wide_approver_ids_for_team(team)
        # The manager may join the roster and one chain; the other team-wide
        # holder still staffs steps from the Approvers tab.
        self.assertNotIn(manager.pk, ids)
        self.assertIn(other.pk, ids)


class EligibleApproverScopeTests(TestCase):
    """The approver picker offers exactly the wide holders routing would use."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@scope.test",
            email="hr@scope.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        self.client.force_authenticate(self.hr)
        self.roles = ensure_roles("supervisor", "registrar")
        self.campus_a = Campus.objects.create(name="Campus A", code="campus-a")
        self.campus_b = Campus.objects.create(name="Campus B", code="campus-b")
        self.academic_a = make_team(
            "Campus A Faculty", ("supervisor",), campus=self.campus_a.name
        )
        self.academic_b = make_team(
            "Campus B Faculty", ("supervisor",), campus=self.campus_b.name
        )
        self.admin = make_team("Central Administration", ("supervisor",))

    def candidates(self, team, role):
        response = self.client.get(
            f"{TEAMS_URL}eligible-approvers/",
            {"team": team.pk, "role": role.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return {row["id"] for row in response.data["candidates"]}

    def test_a_campus_holder_is_offered_at_their_campus_only(self):
        holder = make_employee(
            "campus-a-holder@scope.test",
            category=EmployeeProfile.Category.ACADEMIC,
        )
        CampusRoleAssignment.objects.create(
            campus=self.campus_a, role=self.roles["supervisor"], user=holder
        )
        supervisor = self.roles["supervisor"]

        self.assertIn(holder.pk, self.candidates(self.academic_a, supervisor))
        self.assertNotIn(holder.pk, self.candidates(self.academic_b, supervisor))
        # A campus holding never reaches an administration team.
        self.assertNotIn(holder.pk, self.candidates(self.admin, supervisor))

    def test_an_institution_holder_is_offered_to_administration_only(self):
        holder = make_employee("registrar@scope.test")
        grant_approver_role(holder, "registrar", institution_wide=True)
        registrar = self.roles["registrar"]

        self.assertIn(holder.pk, self.candidates(self.admin, registrar))
        self.assertNotIn(holder.pk, self.candidates(self.academic_a, registrar))


def make_manager(team, email: str, *, role_code: str = "supervisor"):
    """A designated manager with an employee record but no team yet."""
    user = User.objects.create_user(
        username=email,
        email=email,
        password=DEV_PASSWORD,
        first_name="Team",
        last_name="Manager",
        role=User.Role.EMPLOYEE,
    )
    role = ensure_roles(role_code)[role_code]
    TeamRoleAssignment.objects.create(
        team=team, role=role, user=user, is_team_manager=True
    )
    EmployeeProfile.objects.create(
        user=user,
        faculty="Faculty of Science",
        category=team.category,
        grade="B",
    )
    return user


class ManagerOwnChainTests(TestCase):
    """A manager joins their own team and one of its chains, and only one."""

    def setUp(self):
        self.client = APIClient()  # type: ignore[assignment]
        self.hr = User.objects.create_user(
            username="hr@manager-scope.test",
            email="hr@manager-scope.test",
            password=DEV_PASSWORD,
            role=User.Role.HR,
        )
        self.team = make_team("Managed Team", ("supervisor", "hod"))
        self.manager = make_manager(self.team, "manager@manager-scope.test")
        self.second_chain = make_workflow(
            "Managed Team Second Chain", ("supervisor",)
        )
        self.second_chain.team = self.team
        self.second_chain.save(update_fields=["team"])

    def test_the_manager_is_offered_on_their_own_rosters_candidate_list(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            f"{TEAMS_URL}{self.team.pk}/member-candidates/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.manager.pk, {row["user_id"] for row in response.data})

    def test_the_manager_may_add_themselves_to_their_own_team(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"{TEAMS_URL}{self.team.pk}/members/",
            {"user": self.manager.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.manager.employee_profile.refresh_from_db()
        self.assertEqual(self.manager.employee_profile.team_id, self.team.pk)

    def test_once_on_a_team_the_manager_leaves_other_teams_candidate_lists(self):
        other = make_team("Unrelated Team", ("supervisor",))
        self.manager.employee_profile.team = self.team
        self.manager.employee_profile.save(update_fields=["team"])

        self.client.force_authenticate(self.hr)
        response = self.client.get(f"{TEAMS_URL}{other.pk}/member-candidates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.manager.pk, {row["user_id"] for row in response.data})

    def test_once_on_one_chain_the_manager_is_not_offered_to_another(self):
        self.manager.employee_profile.team = self.team
        self.manager.employee_profile.save(update_fields=["team"])
        self.client.force_authenticate(self.manager)

        first = self.client.post(
            f"{WORKFLOWS_URL}{self.team.workflow_id}/members/",
            {"user": self.manager.pk},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)

        pool = self.client.get(
            f"{TEAMS_URL}{self.team.pk}/workflow-member-pool/",
            {"workflow": self.second_chain.pk},
        )
        self.assertEqual(pool.status_code, status.HTTP_200_OK, pool.data)
        self.assertNotIn(
            self.manager.pk, {row["user"] for row in pool.data["available"]}
        )
        elsewhere = {
            row["user"]: row for row in pool.data["assigned_elsewhere"]
        }
        self.assertIn(self.manager.pk, elsewhere)
        self.assertEqual(
            elsewhere[self.manager.pk]["workflow_id"], self.team.workflow_id
        )

        second = self.client.post(
            f"{WORKFLOWS_URL}{self.second_chain.pk}/members/",
            {"user": self.manager.pk},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user", second.data)


class MultiHeldStageSkipsForwardTests(TestCase):
    """An applicant holding several stages is skipped past the highest one."""

    def build_chain(self):
        """``supervisor -> hod -> registrar -> dvc`` with ``applicant`` placed.

        Only the supervisor step is staffed to begin with, so ``hod`` and
        ``registrar`` are resolved by whichever wide holding a test installs.
        That is the shape a team-wide or institution-wide holder actually routes
        through.
        """
        workflow = make_workflow(
            "Scoped Admin Chain", ("supervisor", "hod", "registrar", "dvc")
        )
        team = make_team("Scoped Admin Team", ("supervisor",), workflow=workflow)
        workflow.team = team
        workflow.save(update_fields=["team"])
        applicant = make_employee("applicant@scope.test", team=team)
        sections = {
            section.approver_role.code: section
            for section in workflow.sections.select_related("approver_role")
        }
        dvc = make_employee("dvc@scope.test")
        grant_approver_role(dvc, "dvc", institution_wide=True)
        return workflow, team, applicant, sections, dvc

    def definitions(self, applicant):
        return DatabaseWorkflowProvider().get_stage_definitions(
            LeaveApplication(employee=applicant)
        )

    def test_appointed_and_institution_wide_roles_skip_past_the_highest(self):
        """The applicant is step one *and* the institution-wide registrar.

        The applicant is enrolled on the team's default chain and holds the
        supervisor step by appointment, and also holds the institution-wide
        registrar role. The highest held stage (registrar) decides where
        the chain opens.
        """
        workflow, team, applicant, sections, dvc = self.build_chain()
        # Appointed to the first step, and the registrar role is institution
        # wide, so the third step resolves to them too.
        appoint_approver_to_section(sections["supervisor"], "supervisor", user=applicant)
        grant_approver_role(applicant, "registrar", institution_wide=True)
        # Enrol the applicant on the team's default chain (they are an ordinary
        # member of one chain at a time, per design).
        WorkflowMember.objects.create(
            workflow=team.workflow,
            user=applicant,
            team=team,
            is_wide_approver=False,
        )

        definitions = self.definitions(applicant)

        self.assertEqual(
            [(d.role, d.skipped) for d in definitions],
            [
                ("supervisor", True),
                ("hod", True),
                ("registrar", True),
                ("dvc", False),
            ],
        )
        for definition in definitions:
            if not definition.skipped:
                self.assertNotIn(applicant.pk, definition.approver_user_ids)
        self.assertEqual(definitions[-1].approver_user_ids, (dvc.pk,))

    def test_a_team_wide_holder_is_skipped_forward_from_their_stage(self):
        """A team-wide holder is skipped at their stage, and everything below.

        The applicant holds `hod` team-wide and is enrolled on the team's
        default chain, so they route through it. The skip-forward routing
        then skips their stage and everything below."""
        workflow, team, applicant, sections, dvc = self.build_chain()
        registrar = make_employee("registrar@scope.test")
        grant_approver_role(registrar, "registrar", institution_wide=True)
        # The applicant holds `hod` team-wide; the step is not appointed to
        # them, so the holding is what resolves it.
        TeamRoleAssignment.objects.create(
            team=team, role=ensure_roles("hod")["hod"], user=applicant
        )
        # Enrol the applicant on the team's default chain (they are an ordinary
        # member of one chain at a time, per design).
        WorkflowMember.objects.create(
            workflow=team.workflow,
            user=applicant,
            team=team,
            is_wide_approver=False,
            added_by=self.hr if hasattr(self, 'hr') else None,
        )

        definitions = self.definitions(applicant)

        # The applicant's highest held step is `hod`, so the supervisor step
        # below it is skipped too: routing never moves backwards.
        self.assertEqual(
            [(d.role, d.skipped) for d in definitions],
            [
                ("supervisor", True),
                ("hod", True),
                ("registrar", False),
                ("dvc", False),
            ],
        )
        for definition in definitions:
            if not definition.skipped:
                self.assertNotIn(applicant.pk, definition.approver_user_ids)
