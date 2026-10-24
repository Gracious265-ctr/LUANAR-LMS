"""Seed the fourteen accounts an end-to-end walk of the whole system needs.

:func:`seed_demo_data` builds the smallest thing that routes: one administration
team, a Supervisor -> HOD -> Registrar chain, and five applicants. That is right
for clicking one application through by hand and wrong for testing the system,
which has four other capacities nobody can sign in as, no campus, and no
academic team.

This command builds the full picture — fourteen people on ``@e2e.luanar``, kept
on a separate address from the demo fixture so the two seeds can coexist on one
dev database without taking each other's accounts:

* **HR** (``hr@``) — the account that configures the institution and creates
  teams, so the configuration surfaces have somebody to sign in as.
* **Registrar** (``registrar@``) and **Deputy Vice-Chancellor** (``dvc@``) — the
  two institution-wide offices. A role becomes institution-wide the moment its
  first holder is assigned (:func:`organisation.services.create_role_assignment`
  promotes the flag), so the holdings are written *before* either team exists:
  selecting the role in a chain is what appoints the holder, and the appointment
  needs the promotion to already have happened.
* **Supervisor**, **Head of Department** — the team-scoped approvers of the
  administration chain.
* **Dean**, **Campus Registrar** — the academic chain's two capacities.
* **Seven employees** — four on the administration team, three on the academic
  one, so each chain has applicants and neither account is ever the only
  approver of a step it might itself apply through.

Two teams are built through the same service HR's screens call, so the seed
cannot write a graph the product would refuse:

``Registry Operations`` (administration)
    Supervisor -> HOD -> Registrar -> DVC. The last two steps are written
    unstaffed; ``create_team`` appoints the institution-wide holder of each,
    which is the only way an office like the Vice-Chancellor's can staff a
    step a team cannot appoint.
``Main Campus Academic`` (academic, at Main Campus)
    Dean -> Campus Registrar. The Dean is a team member and is appointed by
    hand; the Campus Registrar step is left unstaffed because a campus-wide
    holder resolves it *without* an appointment, which is what a campus-wide
    holding is for.

The Campus Registrar role is deliberately created **not** institution-wide.
The two are mutually exclusive in the model (a campus-wide holding is refused
for an institution-wide role) and they mean different things: an institution-wide
approver may not serve an academic team at all, so a campus registrar modelled
that way could never approve for the campus it exists to serve.

Idempotent on natural keys: accounts are topped up, holdings are skipped when
this account already holds them, and an existing team is reused rather than
rewritten. An office has exactly one holder, so a holding written by another
seed is *moved* to this account rather than duplicated — the step it staffed
still resolves, now to the account this command is meant to hand out. Re-running
is safe against a database that already carries this seed, the demo seed, or
both.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leave.models import FinancialYear, GradeEntitlement
from leave_types.models import LeaveType
from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    RoleAssignment,
)
from roles.services import (
    RoleActionError,
    create_campus_role_assignment,
    create_role_assignment,
    create_team_role_assignment,
    remove_role_assignment,
    set_team_manager,
)
from teams.models import Team, TeamRoleAssignment
from users.models import EmployeeProfile
from chains.models import WorkflowMember
from chains.services import (
    add_section_member,
    assign_workflow_member,
    create_team,
    validate_team,
)

User = get_user_model()

DEV_PASSWORD = "testpass123"
ACCOUNT_DOMAIN = "e2e.luanar"

CAMPUS_NAME = "Main Campus"
CAMPUS_CODE = "main-campus"

TEAM_ADMIN_NAME = "Registry Operations"
TEAM_ADMIN_CODE = "registry-operations"
TEAM_CAMPUS_NAME = "Main Campus Academic"
TEAM_CAMPUS_CODE = "main-campus-academic"

# Who runs the administration team, and through which team-wide role. A manager
# is a team-wide approver who additionally runs the team's own roster and chains
# — the capacity the Teams app is scoped to. The HOD is a natural manager: the
# role is not institution-wide (a manager holds a *team*-wide role), and the
# person is an administration employee, matching the team's category.
TEAM_ADMIN_MANAGER_USERNAME = "hod"
TEAM_ADMIN_MANAGER_ROLE = "hod"

# The six roles the product ships, mirroring ``workflows.testing.ROLE_SPECS``.
# ``is_institution_wide`` is written explicitly because it is behaviour, not
# decoration: registrar and DVC are held institution-wide, and campus_registrar
# must *not* be, or the campus-wide holding below is refused outright.
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
    "dean": {
        "label": "Dean",
        "description": "Dean of the applicant's faculty.",
        "history_scope": ApproverRole.HistoryScope.SAME_FACULTY,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    "registrar": {
        "label": "Registrar",
        "description": "Institution-wide registrar; approves every application.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    "campus_registrar": {
        "label": "Campus Registrar",
        "description": "Campus-wide registrar; approves every application at "
        "their campus.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    "dvc": {
        "label": "Deputy Vice-Chancellor",
        "description": "Deputy Vice-Chancellor; final institution-wide approval.",
        "history_scope": ApproverRole.HistoryScope.CURRENT_FINANCIAL_YEAR,
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
}

# ``team`` is the key of the team the account belongs to, or None where the
# account deliberately has no team: an institution-wide office approves from
# outside any team, and HR is a configuration surface rather than a chain step.
ROLE_ACCOUNTS = [
    {
        "username": "hr",
        "first_name": "Anna",
        "last_name": "Phiri",
        "role": "hr",
        "grade": "G",
        "category": "administration",
        "team": None,
    },
    {
        "username": "dvc",
        "first_name": "David",
        "last_name": "Mwale",
        "role": "approver",
        "grade": "G",
        "category": "administration",
        "team": None,
    },
    {
        "username": "registrar",
        "first_name": "Peter",
        "last_name": "Gondwe",
        "role": "approver",
        "grade": "G",
        "category": "administration",
        "team": None,
    },
    {
        "username": "supervisor",
        "first_name": "Mary",
        "last_name": "Banda",
        "role": "approver",
        "grade": "G",
        "category": "administration",
        "team": "admin",
    },
    {
        "username": "hod",
        "first_name": "James",
        "last_name": "Tembo",
        "role": "approver",
        "grade": "G",
        "category": "administration",
        "team": "admin",
    },
    {
        "username": "dean",
        "first_name": "Sarah",
        "last_name": "Nyirenda",
        "role": "approver",
        "grade": "G",
        "category": "academic",
        "team": "campus",
    },
    {
        "username": "campus-registrar",
        "first_name": "Andrew",
        "last_name": "Kumwenda",
        "role": "approver",
        "grade": "G",
        "category": "academic",
        "team": None,
    },
]

EMPLOYEE_ACCOUNTS = [
    ("employee1", "Chikondi", "Banda", "admin"),
    ("employee2", "Thandiwe", "Phiri", "admin"),
    ("employee3", "Mphatso", "Gondwe", "admin"),
    ("employee4", "Yamikani", "Tembo", "admin"),
    ("employee5", "Grace", "Mwale", "campus"),
    ("employee6", "Limbani", "Kachale", "campus"),
    ("employee7", "Tadala", "Chirwa", "campus"),
]


class Command(BaseCommand):
    help = (
        "Seed fourteen end-to-end test accounts (HR, DVC, Registrar, Supervisor, "
        "HOD, Dean, Campus Registrar and seven employees), two routable teams, "
        "the campus their chains hang off, and baseline leave config. Idempotent "
        "and safe to re-run against the dev database."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self._accounts = {}
        for spec in ROLE_ACCOUNTS:
            self._accounts[spec["username"]] = self._ensure_user(spec)
        for local, first_name, last_name, team_key in EMPLOYEE_ACCOUNTS:
            self._accounts[local] = self._ensure_user(
                {
                    "username": local,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": User.Role.EMPLOYEE,
                }
            )

        for spec in ROLE_ACCOUNTS:
            self._ensure_profile(
                spec["username"],
                grade=spec["grade"],
                category=spec["category"],
            )
        for local, _first, _last, team_key in EMPLOYEE_ACCOUNTS:
            # An academic team is staffed by Academic employees, matching the
            # campus the team sits at; the administration team is not.
            self._ensure_profile(
                local,
                grade="B",
                category=(
                    EmployeeProfile.Category.ACADEMIC
                    if team_key == "campus"
                    else EmployeeProfile.Category.ADMINISTRATION
                ),
            )

        roles = self._ensure_roles()

        campus = self._ensure_campus()
        self._ensure_institution_wide_holding(
            role=roles["registrar"], user=self._account("registrar")
        )
        self._ensure_institution_wide_holding(
            role=roles["dvc"], user=self._account("dvc")
        )
        self._ensure_campus_holding(
            campus=campus,
            role=roles["campus_registrar"],
            user=self._account("campus-registrar"),
        )

        admin_team = self._ensure_admin_team(roles=roles)
        campus_team = self._ensure_campus_team(roles=roles, campus=campus)

        # The office can change hands after a chain was written (the take-over
        # above does exactly that), which leaves a wide step naming somebody who
        # no longer holds it. Re-point it rather than hand back a team that
        # reports as broken.
        self._sync_institution_wide_sections(team=admin_team)
        self._sync_institution_wide_sections(team=campus_team)

        self._staff(
            team=admin_team,
            members=[
                self._account(local)
                for local, _first, _last, key in EMPLOYEE_ACCOUNTS
                if key == "admin"
            ],
        )
        self._staff(
            team=campus_team,
            members=[
                self._account(local)
                for local, _first, _last, key in EMPLOYEE_ACCOUNTS
                if key == "campus"
            ],
        )

        self._ensure_team_manager(team=admin_team, roles=roles)

        self._ensure_leave_types()

        self._report(campus=campus, admin_team=admin_team, campus_team=campus_team)

    # ------------------------------------------------------------------ people

    def _account(self, local: str) -> User:
        return self._accounts[local]

    @staticmethod
    def _email(local: str) -> str:
        return f"{local}@{ACCOUNT_DOMAIN}"

    def _ensure_user(self, spec: dict) -> User:
        email = self._email(spec["username"])
        user = User.objects.filter(username=email).first()
        if user is None:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=DEV_PASSWORD,
                first_name=spec.get("first_name", ""),
                last_name=spec.get("last_name", ""),
                role=spec.get("role", User.Role.EMPLOYEE),
            )
            self.stdout.write(self.style.SUCCESS(f"  created {email}"))
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
        # A seeded account must be able to sign in: a stripped password is
        # restored, an unusable one repaired, and a retired one brought back.
        if not user.has_usable_password():
            user.set_password(DEV_PASSWORD)
            changed.append("password")
        if not user.is_active:
            user.is_active = True
            changed.append("is_active")
        if changed:
            user.save(update_fields=changed)
        return user

    def _ensure_profile(self, local: str, *, grade: str, category: str) -> None:
        EmployeeProfile.objects.update_or_create(
            user=self._account(local),
            defaults={
                "grade": grade,
                "category": category,
                "faculty": "Administration"
                if category == EmployeeProfile.Category.ADMINISTRATION
                else "Faculty of Science",
            },
        )

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

    def _ensure_campus(self) -> Campus:
        campus, created = Campus.objects.get_or_create(
            code=CAMPUS_CODE,
            defaults={"name": CAMPUS_NAME, "is_active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  created campus {campus.name}"))
        return campus

    def _ensure_institution_wide_holding(self, *, role: ApproverRole, user: User):
        """Give ``role`` its single institution-wide holder.

        A role has exactly one institution-wide approver, so when somebody else
        already holds the office the holding is *moved* rather than skipped: a
        seed account that cannot act is worse than a demo account losing a
        holding it never needs, because the step it staffed still resolves —
        it resolves to whoever holds the office, which is now this account.
        ``seed_demo_data`` guards its own assignment the same way, so whichever
        command runs last leaves its registrar in the chair and neither
        command's chain is left unstaffed.
        """
        holder = RoleAssignment.objects.filter(role=role).select_related("user").first()
        if holder is not None and holder.user_id == user.pk:
            return user
        if holder is not None:
            self.stdout.write(
                self.style.WARNING(
                    f'  "{role.label}" was held by {holder.user.username}; the '
                    f"holding moved to {user.username} so this account can act."
                )
            )
            try:
                remove_role_assignment(assignment=holder, actor=user)
            except RoleActionError as exc:
                raise CommandError(
                    f'Could not move the "{role.label}" holding: {exc.message}'
                ) from exc
        try:
            create_role_assignment(user=user, role=role, actor=user)
        except RoleActionError as exc:
            raise CommandError(
                f'Could not assign "{role.label}" institution-wide: {exc.message}'
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"  {user.username} holds {role.label} institution-wide"
            )
        )
        return user

    def _ensure_campus_holding(
        self, *, campus: Campus, role: ApproverRole, user: User
    ) -> None:
        """Give ``role`` its one campus-wide holder at ``campus``."""
        existing = (
            CampusRoleAssignment.objects.filter(campus=campus, role=role)
            .select_related("user")
            .first()
        )
        if existing is not None and existing.user_id == user.pk:
            return
        if existing is not None:
            self.stdout.write(
                self.style.WARNING(
                    f'  "{role.label}" was held at {campus.name} by '
                    f"{existing.user.username}; the holding moved to "
                    f"{user.username} so this account can act."
                )
            )
        try:
            create_campus_role_assignment(
                campus=campus, role=role, user=user, actor=user
            )
        except RoleActionError as exc:
            raise CommandError(
                f'Could not assign "{role.label}" at {campus.name}: {exc.message}'
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"  {user.username} holds {role.label} at {campus.name}"
            )
        )

    # -------------------------------------------------------------------- team

    def _ensure_admin_team(self, *, roles: dict) -> Team:
        team = Team.objects.filter(code=TEAM_ADMIN_CODE).first()
        if team is not None:
            self.stdout.write(f"  team {team.name} already exists; reusing it")
            return team

        # Registrar and DVC steps are written unstaffed on purpose. Their roles
        # are institution-wide, so create_team appoints the single holder —
        # which is why the holdings above are written first: the appointment
        # reads the promotion the assignment made.
        team = create_team(
            actor=self._account("hr"),
            data={
                "name": TEAM_ADMIN_NAME,
                "code": TEAM_ADMIN_CODE,
                "description": (
                    "Administration team seeded for end-to-end testing of the "
                    "leave approval flow."
                ),
                "category": Team.Category.ADMINISTRATION,
            },
            workflow_config={
                "name": f"{TEAM_ADMIN_NAME} workflow",
                "sections": [
                    {
                        "order": 1,
                        "name": "Supervisor Review",
                        "approver_role": roles["supervisor"].code,
                        "approver": self._account("supervisor").pk,
                    },
                    {
                        "order": 2,
                        "name": "HOD Review",
                        "approver_role": roles["hod"].code,
                        "approver": self._account("hod").pk,
                    },
                    {
                        "order": 3,
                        "name": "Registrar Review",
                        "approver_role": roles["registrar"].code,
                        "approver": None,
                    },
                    {
                        "order": 4,
                        "name": "DVC Review",
                        "approver_role": roles["dvc"].code,
                        "approver": None,
                    },
                ],
            },
        )
        self.stdout.write(self.style.SUCCESS(f"  created team {team.name}"))
        return team

    def _ensure_campus_team(self, *, roles: dict, campus: Campus) -> Team:
        team = Team.objects.filter(code=TEAM_CAMPUS_CODE).first()
        if team is not None:
            self.stdout.write(f"  team {team.name} already exists; reusing it")
            return team

        # The Campus Registrar step is left unstaffed: a campus-wide holder
        # resolves it without an appointment, so naming one here would only
        # pin the step to a person the holding is meant to free it from.
        team = create_team(
            actor=self._account("hr"),
            data={
                "name": TEAM_CAMPUS_NAME,
                "code": TEAM_CAMPUS_CODE,
                "description": (
                    "Academic team at the Main Campus, seeded for end-to-end "
                    "testing of a campus-scoped approval chain."
                ),
                "category": Team.Category.ACADEMIC,
                "campus": campus,
            },
            workflow_config={
                "name": f"{TEAM_CAMPUS_NAME} workflow",
                "sections": [
                    {
                        "order": 1,
                        "name": "Dean Review",
                        "approver_role": roles["dean"].code,
                        "approver": self._account("dean").pk,
                    },
                    {
                        "order": 2,
                        "name": "Campus Registrar Review",
                        "approver_role": roles["campus_registrar"].code,
                        "approver": None,
                    },
                ],
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"  created team {team.name} at {campus.name}")
        )
        return team

    def _ensure_team_manager(self, *, team: Team, roles: dict) -> None:
        """Designate the administration team's manager.

        A manager is a team-wide holder carrying the manager flag, written
        through the same ``is_team_manager`` path HR uses — not by setting the
        column directly. Kept as its own idempotent step rather than folded into
        :func:`create_team`'s ``manager`` kwarg, because the kwarg only runs on
        the create, and a re-run on an existing team must still leave the
        designation in place. Writing it here also means the whole thing is
        exercised through the product service, which is the point of the fixture.
        """
        user = self._account(TEAM_ADMIN_MANAGER_USERNAME)
        role = roles[TEAM_ADMIN_MANAGER_ROLE]
        existing = TeamRoleAssignment.objects.filter(team=team, role=role).first()
        if existing is not None and existing.user_id == user.pk:
            if existing.is_team_manager:
                self.stdout.write(
                    f"  {user.username} already manages {team.name}; leaving it"
                )
                return
            set_team_manager(assignment=existing, actor=self._account("hr"))
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {user.username} is now manager of {team.name}"
                )
            )
            return

        # ``create_team_role_assignment`` writes the holder and the manager flag
        # in one atomic step, so there is nothing further to set: the
        # designation travelled with the assignment.
        create_team_role_assignment(
            team=team,
            role=role,
            user=user,
            actor=self._account("hr"),
            is_team_manager=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  {user.username} holds {role.label} for {team.name} "
                f"as its manager"
            )
        )

    def _sync_institution_wide_sections(self, *, team: Team) -> None:
        """Re-point a wide step whose office has moved.

        :func:`create_team` appoints the institution-wide holder the moment the
        role is selected in a chain, because the team-scoped picker cannot
        offer them. That appointment is a snapshot of who held the office when
        the chain was written, and an office can change hands afterwards. A
        step still naming the previous holder is configuration nobody chose and
        it fails the readiness check, so it is re-pointed to the holder the role
        has now — which is what the appointment would have written had it been
        made today.
        """
        workflow = team.workflow
        if workflow is None:
            return
        for section in workflow.sections.select_related("approver_role"):
            role = section.approver_role
            if not role.is_institution_wide:
                continue
            holders = list(
                RoleAssignment.objects.filter(role=role, user__is_active=True)
                .values_list("user_id", flat=True)
            )
            if len(holders) != 1 or section.approver_id == holders[0]:
                continue
            holder = User.objects.get(pk=holders[0])
            add_section_member(section=section, user=holder, actor=self._account("hr"))
            self.stdout.write(
                self.style.WARNING(
                    f'  "{section.name}" re-pointed to {holder.username}, the '
                    f"current {role.label}."
                )
            )

    def _staff(self, *, team: Team, members: list[User]) -> None:
        workflow = team.workflow
        if workflow is None:
            raise CommandError(f"Team {team.name} has no workflow to staff.")
        for member in members:
            # Read the profile off the account itself rather than querying it
            # fresh: ``assign_workflow_member`` reads the same cached related
            # object, so a second query would hand it the pre-save team.
            profile = member.employee_profile
            if profile.team_id != team.pk:
                profile.team = team
                profile.save(update_fields=["team"])
            if not WorkflowMember.objects.filter(
                workflow=workflow, user=member
            ).exists():
                assign_workflow_member(
                    workflow=workflow, user=member, actor=self._account("hr")
                )

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

    def _report(self, *, campus, admin_team, campus_team) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("End-to-end test profiles ready."))
        self.stdout.write(f"  Password:  {DEV_PASSWORD} (every account)")
        self.stdout.write(f"  Campus:    {campus.name} ({campus.code})")

        for team, chain in (
            (
                admin_team,
                "Supervisor -> HOD -> Registrar -> DVC",
            ),
            (
                campus_team,
                "Dean -> Campus Registrar",
            ),
        ):
            readiness = validate_team(team)
            if readiness.issues:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {team.name}: NOT READY — {len(readiness.issues)} "
                        "issue(s)"
                    )
                )
                for issue in readiness.issues:
                    self.stdout.write(f"      - {issue.message}")
            else:
                self.stdout.write(
                    f"  {team.name} ({team.get_status_display()}): ready — {chain}"
                )

        self.stdout.write("  Accounts:")
        for spec in ROLE_ACCOUNTS:
            self.stdout.write(
                f"    - {self._email(spec['username'])} "
                f"({spec['first_name']} {spec['last_name']}, "
                f"{spec['role']})"
            )
        for local, first_name, last_name, team_key in EMPLOYEE_ACCOUNTS:
            team = admin_team if team_key == "admin" else campus_team
            self.stdout.write(
                f"    - {self._email(local)} ({first_name} {last_name}, "
                f"employee, {team.name})"
            )
        self.stdout.write(
            f"  Institution-wide: registrar@{ACCOUNT_DOMAIN} (Registrar), "
            f"dvc@{ACCOUNT_DOMAIN} (Deputy Vice-Chancellor)"
        )
        self.stdout.write(
            f"  Campus-wide:      campus-registrar@{ACCOUNT_DOMAIN} "
            f"(Campus Registrar at {campus.name})"
        )
