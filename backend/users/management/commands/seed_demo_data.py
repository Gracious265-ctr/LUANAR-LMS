"""Seed a realistic, routable team so the leave flow can be exercised by hand.

Everything else in this repository builds its fixtures inside a test database,
which is thrown away when the test ends. That is the wrong shape for "log in and
click through an approval": a person needs a team that exists against the *dev*
database, with accounts they can actually sign in as.

This command builds the smallest configuration that routes end to end:

* three approver roles — ``supervisor``, ``hod`` and an institution-wide
  ``registrar``;
* an administration team (no campus) that owns one workflow whose three sections
  are Supervisor → HOD → Registrar;
* a supervisor and a registrar account, five ordinary employees, and the
  pre-existing superuser appointed as **HOD** — which is the only way an account
  can hold HOD, because routing is configuration, not ``User.role``;
* baseline leave configuration (an active financial year, a plannable Annual
  Leave type and the grade band that offers it) so an employee can plan and
  apply, not just be routed.

The team is created through the same service HR's screens call
(:func:`workflows.services.create_team`), so the seed cannot build a graph the
product would refuse — it either validates or it fails. Creating a team puts it
in force, so there is no separate activation step.

Idempotent on natural keys: re-running tops the roster and the leave config up
and leaves an already-built team alone, so it is safe to run against a database
that already has the demo data.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leave.models import FinancialYear, GradeEntitlement
from leave_types.models import LeaveType
from users.models import EmployeeProfile
from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment (
    ApproverRole,
)
from teams.models import (
    Team,
)
from chains.services import (
    assign_workflow_member,
    create_team,
)
from roles.services import (
    create_role_assignment,
)

User = get_user_model()

DEV_PASSWORD = "testpass123"

SUPERUSER_USERNAME = "admin@test.luanar"

TEAM_NAME = "Registry Services"
TEAM_CODE = "registry-services"
TEAM_DESCRIPTION = (
    "Administration team seeded for testing the leave approval flow."
)

# Mirror workflows.testing.ROLE_SPECS: the same six roles the product ships, of
# which three are needed for this chain. registrar is institution-wide by
# definition, which is what lets its step resolve without a team member holding
# it.
ROLE_SPECS = {
    "supervisor": {
        "label": "Supervisor",
        "description": "Line manager of the applicant.",
        "history_scope": ApproverRole.HistoryScope.ALL,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "hod": {
        "label": "Head of Department",
        "description": "Head of the applicant's department.",
        "history_scope": ApproverRole.HistoryScope.SAME_TEAM,
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    "registrar": {
        "label": "Registrar",
        "description": "Institution-wide registrar; approves every application.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
}

SUPERVISOR = {
    "username": "supervisor@test.luanar",
    "first_name": "Linda",
    "last_name": "Mwase",
    "role": "approver",
}

REGISTRAR = {
    "username": "registrar@test.luanar",
    "first_name": "Patrick",
    "last_name": "Kachale",
    "role": "approver",
}

EMPLOYEES = [
    ("employee1@test.luanar", "Chikondi", "Banda"),
    ("employee2@test.luanar", "Thandiwe", "Phiri"),
    ("employee3@test.luanar", "Mphatso", "Gondwe"),
    ("employee4@test.luanar", "Yamikani", "Tembo"),
    ("employee5@test.luanar", "Grace", "Mwale"),
]


class Command(BaseCommand):
    help = (
        "Seed a routable administration team, its Supervisor/HOD/Registrar "
        "chain, five employees, approver accounts and baseline leave config. "
        "Idempotent and safe to re-run against the dev database."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._get_superuser()

        roles = self._ensure_roles()

        supervisor = self._ensure_user(SUPERVISOR)
        registrar = self._ensure_user(REGISTRAR)
        self._ensure_profile(supervisor, grade="G")
        self._ensure_profile(registrar, grade="G")

        # The superuser is the HOD. Routing is configuration, so HOD is conferred
        # by the section appointment written below, never by User.role; the
        # employee record only lets the appointment pass the membership rule.
        self._ensure_profile(admin, grade="G")

        employees = []
        for username, first_name, last_name in EMPLOYEES:
            employee = self._ensure_user(
                {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "employee",
                }
            )
            self._ensure_profile(employee, grade="B")
            employees.append(employee)

        self._ensure_registrar_holding(role=roles["registrar"], user=registrar, actor=admin)

        team = self._ensure_team(
            roles=roles,
            supervisor=supervisor,
            hod=admin,
        )

        self._staff_team(team=team, employees=employees, actor=admin)

        self._ensure_leave_types()

        self._report(team=team, admin=admin, supervisor=supervisor, registrar=registrar)

    # ------------------------------------------------------------------ people

    def _get_superuser(self):
        admin = User.objects.filter(username=SUPERUSER_USERNAME).first()
        if admin is None:
            raise CommandError(
                f"No superuser '{SUPERUSER_USERNAME}' exists. Create it first:\n"
                "  DJANGO_SUPERUSER_PASSWORD=testpass123 "
                f"uv run manage.py createsuperuser --noinput "
                f"--username {SUPERUSER_USERNAME} --email {SUPERUSER_USERNAME}"
            )
        return admin

    def _ensure_user(self, spec: dict):
        user = User.objects.filter(username=spec["username"]).first()
        if user is None:
            user = User.objects.create_user(
                username=spec["username"],
                email=spec["username"],
                password=DEV_PASSWORD,
                first_name=spec.get("first_name", ""),
                last_name=spec.get("last_name", ""),
                role=spec.get("role", User.Role.EMPLOYEE),
            )
            self.stdout.write(self.style.SUCCESS(f"  created {spec['username']}"))
            return user

        changed = []
        if spec.get("first_name") and user.first_name != spec["first_name"]:
            user.first_name = spec["first_name"]
            changed.append("first_name")
        if spec.get("last_name") and user.last_name != spec["last_name"]:
            user.last_name = spec["last_name"]
            changed.append("last_name")
        if spec.get("role") and user.role != spec["role"]:
            user.role = spec["role"]
            changed.append("role")
        if changed:
            user.save(update_fields=changed)
        # A seeded account must be able to sign in, so a stripped password is
        # restored and an unusable one repaired.
        if not user.has_usable_password():
            user.set_password(DEV_PASSWORD)
            user.save(update_fields=["password"])
        return user

    def _ensure_profile(self, user, *, grade: str) -> EmployeeProfile:
        profile, _ = EmployeeProfile.objects.update_or_create(
            user=user,
            defaults={
                "faculty": "Administration",
                "category": EmployeeProfile.Category.ADMINISTRATION,
                "grade": grade,
            },
        )
        return profile

    # ------------------------------------------------------------------- roles

    def _ensure_roles(self) -> dict:
        roles = {}
        for code, spec in ROLE_SPECS.items():
            role, _ = ApproverRole.objects.update_or_create(
                code=code,
                defaults={**spec, "is_active": True},
            )
            roles[code] = role
        return roles

    def _ensure_registrar_holding(self, *, role, user, actor) -> None:
        if role.role_assignments.exists():
            return
        create_role_assignment(user=user, role=role, actor=actor)
        self.stdout.write(
            self.style.SUCCESS(f"  {user.username} holds {role.label} institution-wide")
        )

    # -------------------------------------------------------------------- team

    def _ensure_team(self, *, roles, supervisor, hod) -> Team:
        team = Team.objects.filter(name=TEAM_NAME).first()
        if team is not None:
            return team

        # The registrar section is left unstaffed on purpose: its role is
        # institution-wide, so create_team appoints the role's single holder
        # automatically rather than naming a team member.
        team = create_team(
            actor=hod,
            data={
                "name": TEAM_NAME,
                "code": TEAM_CODE,
                "description": TEAM_DESCRIPTION,
                "category": Team.Category.ADMINISTRATION,
            },
            workflow_config={
                "name": f"{TEAM_NAME} workflow",
                "sections": [
                    {
                        "order": 1,
                        "name": "Supervisor Review",
                        "approver_role": roles["supervisor"].code,
                        "approver": supervisor.pk,
                    },
                    {
                        "order": 2,
                        "name": "HOD Review",
                        "approver_role": roles["hod"].code,
                        "approver": hod.pk,
                    },
                    {
                        "order": 3,
                        "name": "Registrar Review",
                        "approver_role": roles["registrar"].code,
                        "approver": None,
                    },
                ],
            },
        )
        self.stdout.write(self.style.SUCCESS(f"  created team {team.name}"))
        return team

    def _staff_team(self, *, team, employees, actor) -> None:
        workflow = team.workflow
        if workflow is None:
            # Seed uses single workflow per team now
            workflows_list = list(team.workflows.all())
            workflow = workflows_list[0] if workflows_list else None
        if workflow is None:
            raise CommandError(f"Team {team.name} has no workflow to staff.")

        for employee in employees:
            profile = employee.employee_profile
            if profile.team_id != team.pk:
                profile.team = team
                profile.save(update_fields=["team"])
            assign_workflow_member(workflow=workflow, user=employee, actor=actor)

    # -------------------------------------------------------------- leave config

    def _ensure_leave_types(self) -> None:
        today = timezone.localdate()
        year_start = date(today.year, 1, 1)
        year_end = date(today.year, 12, 31)

        year = FinancialYear.objects.filter(
            start_date=year_start, end_date=year_end
        ).first()
        if year is None:
            year = FinancialYear.objects.create(
                start_date=year_start,
                end_date=year_end,
                is_active=True,
            )
        elif not year.is_active:
            FinancialYear.objects.update(is_active=False)
            year.is_active = True
            year.save(update_fields=["is_active"])

        # Refinement unit 06 folded the effective-dated leave rule into the
        # type itself: ``notice_days`` now carries the value the Leave Plans
        # reminder and Unit 14's submission validation both read.
        leave_type, _ = LeaveType.objects.update_or_create(
            code="annual",
            defaults={
                "name": "Annual Leave",
                "is_active": True,
                "plannable": True,
                "notice_days": 7,
                "max_duration_days": 30,
                "requires_supporting_document": False,
                "consumes_annual_entitlement": True,
            },
        )
        GradeEntitlement.objects.update_or_create(
            leave_type=leave_type,
            grade_start="A",
            grade_end="Z",
            defaults={"days": 30, "effective_from": year_start},
        )

    # ------------------------------------------------------------------ report

    def _report(self, *, team, admin, supervisor, registrar) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Leave-flow demo data ready."))
        self.stdout.write(f"  Team:      {team.name} ({team.get_status_display()})")
        self.stdout.write(
            "  Chain:     Supervisor -> HOD -> Registrar"
        )
        self.stdout.write(f"  HOD:        {admin.username} (password: {DEV_PASSWORD})")
        self.stdout.write(
            f"  Supervisor: {supervisor.username} (password: {DEV_PASSWORD})"
        )
        self.stdout.write(
            f"  Registrar: {registrar.username} (password: {DEV_PASSWORD})"
        )
        self.stdout.write("  Employees:")
        for username, first_name, last_name in EMPLOYEES:
            self.stdout.write(
                f"    - {username} ({first_name} {last_name}, password: {DEV_PASSWORD})"
            )
