"""Dev seed for the Unit 16 approver dashboard (DEBUG-only).

Creates the HR-managed approval configuration and submitted leave applications
that flow through it, so the approver dashboard has realistic pending/decided
items for every approver role.

The configuration is seeded in dependency order, because every layer points at
the one before it:

1. **Approver roles** — the six roles the product ships with. ``registrar`` and
   ``campus_registrar`` are institution-wide; the rest are team roles.
2. **Campuses** — reference data teams can optionally belong to.
3. **Workflows** — ordered chains of *sections*, e.g. supervisor → hod → registrar
   → dvc. Each section names the role that may act on it and references it by
   foreign key.
4. **Teams** — each points at one workflow, and the workflow's sections name who
   may act on them.
5. **People** — employees are placed on a team (``EmployeeProfile.team``), which
   is what selects their workflow; approvers are placed on the relevant section
   (``SectionMember``), and the registrar is given the role institution-wide
   (``RoleAssignment``) because they approve for every team.

Sections may hold several members, in which case whichever of them acts first
claims the step. The seed gives each section exactly one member so the dev
dashboard has a predictable pending item per approver; add a second member in the
admin to try the contested case.

So:

* Administration (employee@test.luanar) → supervisor → hod → registrar → dvc
* Academic (science-employee@test.luanar, outside the dean's faculty)
  → hod → dean → registrar → dvc

The registrar resolves through the institution-wide assignment rather than any
team, which keeps the "no team member — fall back to the holder" path exercised
in development rather than only in tests.

Idempotent: every step is ``get_or_create``/``update_or_create`` on a natural key,
and the applications step is guarded by the ``LV-<FY>-800`` reference prefix.
Requires ``seed_dev_users`` first, which this command runs itself.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leave.models import LeaveApplication
from leave.services.submission import submit_application
from leave.services.working_days import holidays_in_range
from users.models import EmployeeProfile, User

FIYEAR_PREFIX = "800"
DEV_PASSWORD = "testpass123"

# The shipped approver roles. Mirrors what migration 0011 backfills, so a
# database that has been migrated and one that has only been seeded end up with
# the same six roles. `update_or_create` on `code` keeps the two in step.
SEED_ROLES = [
    # code, label, description, history_scope, handles_cancellation, wide
    {
        "code": "supervisor",
        "label": "Supervisor",
        "description": "Line manager of the applicant.",
        "history_scope": "all",
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    {
        "code": "hod",
        "label": "Head of Department",
        "description": "Head of the applicant's department.",
        "history_scope": "same_department",
        "handles_cancellation": True,
        "is_institution_wide": False,
    },
    {
        "code": "dean",
        "label": "Dean",
        "description": "Dean of the applicant's faculty.",
        "history_scope": "same_faculty",
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
    {
        "code": "registrar",
        "label": "Registrar",
        "description": "Institution-wide registrar; approves every application.",
        "history_scope": "current_financial_year",
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    {
        "code": "campus_registrar",
        "label": "Campus Registrar",
        "description": "Registrar for a single campus.",
        "history_scope": "current_financial_year",
        "handles_cancellation": False,
        "is_institution_wide": True,
    },
    {
        "code": "dvc",
        "label": "Deputy Vice-Chancellor",
        "description": "Deputy Vice-Chancellor; final institution-wide approval.",
        "history_scope": "current_financial_year",
        "handles_cancellation": False,
        "is_institution_wide": False,
    },
]

SEED_CAMPUSES = [
    ("main", "Main Campus"),
    ("theochrist", "Theo-Christ University Campus"),
]

# name, code, description, campus code, workflow name, [(role code, username)]
SEED_TEAMS = [
    {
        "name": "Administration Team",
        "code": "administration",
        "description": "Central administration staff.",
        "campus": "main",
        "workflow": "Administration Leave Workflow",
        "members": [
            ("supervisor", "supervisor@test.luanar"),
            ("hod", "hod@test.luanar"),
            ("dvc", "dvc@test.luanar"),
        ],
    },
    {
        "name": "Bunda College Team",
        "code": "bunda-college",
        "description": "Academic staff of the School of Education.",
        "campus": "theochrist",
        "workflow": "Academic Leave Workflow",
        "members": [
            ("hod", "hod@test.luanar"),
            ("dean", "dean@test.luanar"),
            ("dvc", "dvc@test.luanar"),
        ],
    },
]

# Employee placement, applied after the teams exist. An employee with no team
# cannot submit: the provider refuses to build a chain and says so.
SEED_EMPLOYEE_TEAMS = {
    "employee@test.luanar": "administration",
    "science-employee@test.luanar": "bunda-college",
}


class Command(BaseCommand):
    help = (
        "Seed submitted leave applications for the Unit 16 approver dashboard "
        "(references LV-<FY>-80001..80007). Requires DEBUG=true and "
        "seed_dev_users first."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_approvals_dev only runs with DEBUG=true.")

        from leave.services import active_financial_year

        from users.management.commands.seed_dev_users import (
            Command as SeedUsersCommand,
        )

        SeedUsersCommand().handle()

        fy = active_financial_year()
        fy_label = (
            f"{fy.start_date.year}-{str(fy.end_date.year)[-2:]}" if fy else None
        )
        if not fy_label:
            raise CommandError("No active financial year configured.")

        self._ensure_second_employee()
        self._seed_configuration()

        prefix = f"LV-{fy_label}-{FIYEAR_PREFIX}"
        if LeaveApplication.objects.filter(
            reference_number__startswith=prefix
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Approvals already seeded (references {prefix}*) — keeping."
                )
            )
        else:
            self._seed_applications(fy_label, prefix)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Created approvals with references {prefix}*."
                )
            )

        self._seed_cancellations(fy_label)
        self._seed_documents(fy_label)

    def _seed_configuration(self):
        """Roles, campuses, workflows, teams, and people — in that order.

        Each layer references the previous one, so the order is the dependency
        order, not a preference. Every step is idempotent on a natural key, so
        re-running the command repairs a partially seeded database instead of
        failing on it.
        """
        roles = self._seed_roles()
        campuses = self._seed_campuses()
        self._seed_workflows(roles)
        self._seed_teams(roles, campuses)
        self._place_people(roles)

    def _seed_roles(self) -> dict:
        """The shipped approver roles, keyed by code.

        ``update_or_create`` rather than ``get_or_create`` on purpose: if an
        admin has edited a label or deactivated a role in development, the next
        seed run restores the shipped configuration instead of silently
        disagreeing with it.
        """
        from workflows.models import ApproverRole

        seeded = {}
        for spec in SEED_ROLES:
            role, created = ApproverRole.objects.update_or_create(
                code=spec["code"],
                defaults={**spec, "is_active": True},
            )
            seeded[spec["code"]] = role
            if created:
                self.stdout.write(self.style.SUCCESS(f"Seeded role '{role.code}'."))
        return seeded

    def _seed_campuses(self) -> dict:
        from workflows.models import Campus

        return {
            code: Campus.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_active": True},
            )[0]
            for code, name in SEED_CAMPUSES
        }

    def _seed_workflows(self, roles: dict) -> None:
        """Workflows whose sections reference approver roles by foreign key.

        ``effective_from`` defaults to the active financial year's start so the
        provider treats the chains as live configuration from day one. Sections
        are rebuilt on every run rather than only on creation: a role retired in
        the admin would otherwise leave the workflow permanently unactivatable
        with no way to repair it from a seed.

        The rebuild is skipped once an application has snapshotted the chain.
        ``ApplicationStage.section_ref`` is ``PROTECT`` because the section a
        running application was materialised from is its frozen history, so the
        database refuses the delete — and would be right to. Replacing the rows a
        live chain points at would detach it from the section that defines it, so
        the repair path is a no-op while anything is in flight.
        """
        from workflows.models import ApplicationStage, Section, Workflow

        from leave.services import active_financial_year

        fy = active_financial_year()
        effective = (fy.start_date if fy else None) or timezone.localdate()

        definitions = [
            (
                "Administration Leave Workflow",
                EmployeeProfile.Category.ADMINISTRATION,
                ("supervisor", "hod", "registrar", "dvc"),
            ),
            (
                "Academic Leave Workflow",
                EmployeeProfile.Category.ACADEMIC,
                ("hod", "dean", "registrar", "dvc"),
            ),
        ]
        for name, category, role_codes in definitions:
            workflow, created = Workflow.objects.update_or_create(
                name=name,
                defaults={
                    "employee_category": category,
                    "effective_from": effective,
                    "is_active": True,
                },
            )
            if ApplicationStage.objects.filter(section_ref__workflow=workflow).exists():
                continue
            workflow.sections.all().delete()
            Section.objects.bulk_create(
                [
                    Section(
                        workflow=workflow,
                        order=index,
                        name=roles[code].label,
                        approver_role=roles[code],
                    )
                    for index, code in enumerate(role_codes, start=1)
                ]
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Seeded workflow '{name}'.")
                )

    def _seed_teams(self, roles: dict, campuses: dict) -> None:
        """Teams, their sections' members, and the institution-wide registrar holding.

        A team points at one workflow, and the workflow's sections are the same
        rows for every team that uses it. The two seeded teams therefore share
        their workflows rather than each having a private copy, which is what
        makes the shared-workflow case real in development; the registrar has no
        section member at all so their institution-wide holding is what resolves.
        """
        from workflows.models import RoleAssignment, SectionMember, Team, Workflow

        for spec in SEED_TEAMS:
            workflow = Workflow.objects.get(name=spec["workflow"])
            team, created = Team.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "campus": campuses.get(spec["campus"]),
                    "workflow": workflow,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Seeded team '{team.name}'."))
            sections = {
                section.approver_role_id: section
                for section in workflow.sections.all()
            }
            for role_code, username in spec["members"]:
                section = sections.get(roles[role_code].pk)
                if section is None:
                    raise CommandError(
                        f"Team '{team.name}' names '{username}' for role "
                        f"'{role_code}', but its workflow "
                        f"'{workflow.name}' has no section for that role."
                    )
                SectionMember.objects.update_or_create(
                    section=section,
                    user=User.objects.get(username=username),
                )

        # The registrar approves for every team, so their holding is
        # institution-wide rather than a membership in each. This is the row that
        # makes the "section role with no member" case work in development.
        registrar_role = roles["registrar"]
        registrar = User.objects.get(username="registrar@test.luanar")
        RoleAssignment.objects.get_or_create(user=registrar, role=registrar_role)

        # The campus registrar is seeded as a holder too, but of no team: with
        # nothing pointing at a campus-specific chain it deliberately resolves to
        # nobody, which is what a half-configured campus should look like.
        RoleAssignment.objects.get_or_create(
            user=User.objects.get(username="dvc@test.luanar"),
            role=roles["campus_registrar"],
        )

    def _place_people(self, roles: dict) -> None:
        """Put employees on a team; that is what picks their workflow."""
        from workflows.models import Team

        teams = {team.code: team for team in Team.objects.all()}
        for username, team_code in SEED_EMPLOYEE_TEAMS.items():
            employee = User.objects.get(username=username)
            profile = EmployeeProfile.objects.filter(user=employee).first()
            if profile is None:
                profile = EmployeeProfile.objects.create(user=employee)
            profile.team = teams[team_code]
            profile.save(update_fields=["team"])

    def _ensure_second_employee(self):
        """An academic outside the Dean's faculty (review-scope boundary).

        Placed on a team by :meth:`_place_people`, not here, so every employee
        gets their team in the same pass.
        """
        user, created = User.objects.get_or_create(
            username="science-employee@test.luanar",
            defaults={
                "email": "science-employee@test.luanar",
                "first_name": "Mphatso",
                "last_name": "Banda",
                "role": User.Role.EMPLOYEE,
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()
        EmployeeProfile.objects.update_or_create(
            user=user,
            defaults={
                "department": "Mathematics",
                "designation": "Lecturer",
                "category": EmployeeProfile.Category.ACADEMIC,
                "faculty": "Faculty of Science",
                "grade": "C",
                "appointment_date": date(2021, 5, 1),
            },
        )
        return user

    def _seed_applications(self, fy_label: str, prefix: str):
        from workflows.services import decide

        employee = User.objects.get(
            username="employee@test.luanar", role=User.Role.EMPLOYEE
        )
        science = User.objects.get(username="science-employee@test.luanar")

        supervisor = User.objects.get(username="supervisor@test.luanar")
        hod = User.objects.get(username="hod@test.luanar")
        registrar = User.objects.get(username="registrar@test.luanar")
        dvc = User.objects.get(username="dvc@test.luanar")
        dean = User.objects.get(username="dean@test.luanar")

        def app(user, seq, label):
            start = self._suitable_start(user, seq)
            return LeaveApplication.objects.create(
                employee=user,
                leave_type_id=1,
                start_date=start,
                end_date=start + timedelta(days=6),
                reason=f"{label} leave (seeded)",
                reference_number=f"{prefix}{seq:03d}",
            )

        def submit(application):
            return submit_application(
                user=application.employee, application_id=application.pk
            )

        def act(application, user, action, comment=""):
            stage = application.current_stage
            return decide(
                application_id=application.pk,
                actor=user,
                action=action,
                comment=comment,
                expected_version=stage.decision_version,
            )

        # Pending at the supervisor.
        pending_supervisor = submit(app(employee, 1, "Annual"))
        # Pending at the hod.
        pending_hod = act(submit(app(employee, 2, "Annual")), supervisor, "approve")
        # Pending at the registrar.
        pending_registrar = act(submit(app(employee, 3, "Annual")), supervisor, "approve")
        pending_registrar = act(pending_registrar, hod, "approve")
        # Fully approved.
        approved = act(submit(app(employee, 4, "Annual")), supervisor, "approve")
        approved = act(approved, hod, "approve")
        approved = act(approved, registrar, "approve")
        act(approved, dvc, "approve")
        # Rejected at the hod.
        rejected = act(submit(app(employee, 5, "Annual")), supervisor, "approve")
        act(rejected, hod, "reject", comment="Documentation missing on this leave.")
        # Correction returned at the dean.
        corrected = act(submit(app(science, 6, "Annual")), hod, "approve")
        act(corrected, dean, "return_for_correction",
            comment="Please correct the leave dates before re-submitting.")
        # Pending at the dean.
        pending_dean = act(submit(app(science, 7, "Annual")), hod, "approve")

        del pending_supervisor, pending_hod, pending_registrar, pending_dean

    def _suitable_start(self, user, seq: int, min_offset_days: int = 0) -> date:
        """A working day giving >= 5 working days' notice, with no clash.

        ``min_offset_days`` pushes the start further out — the cancellation
        scenarios need a fortnight-plus run of future leave so there is something
        to cancel.

        Public holidays are skipped as well as weekends, so a seeded application
        never starts on a day the validation pipeline would reject. Dates that
        overlap an application this person already has are skipped as well: the
        seeded scenarios are all for the same two employees, and as real time
        advances the dates an *earlier* seed run picked drift into the window this
        run is about to use. Without this the command fails with
        ``OVERLAPPING_LEAVE`` on every re-seed, which reads like a regression in
        routing rather than the seed being time-dependent.
        """
        today = timezone.localdate()
        holidays = holidays_in_range(
            today + timedelta(days=1), today + timedelta(days=180)
        )
        taken = [
            (app.start_date, app.end_date)
            for app in LeaveApplication.objects.filter(employee=user)
        ]

        candidate = today
        working_days = 0
        while True:
            candidate += timedelta(days=1)
            if candidate.weekday() >= 5 or candidate in holidays:
                continue
            working_days += 1
            # Six working days' notice, staggered per scenario so the seeded
            # applications do not all pile onto the same week, and never earlier
            # than the caller's own floor.
            if working_days < 6 + (seq % 2) or candidate < today + timedelta(
                days=min_offset_days
            ):
                continue
            end = candidate + timedelta(days=6)
            if any(
                candidate <= existing_end and end >= existing_start
                for existing_start, existing_end in taken
            ):
                continue
            return candidate

    def _seed_cancellations(self, fy_label: str):
        """Unit 18 cancellation scenarios (references LV-<FY>-810NNN).

        Creates approved applications that actually flowed through the real
        workflow, then opens/rejects/approves cancellation requests so the
        supervisor queue and decided tab have realistic items. Idempotent on
        the 810 prefix.
        """
        from leave.cancellations.models import (
            CancellationApprovalStage,
            CancellationRequest,
        )
        from leave.cancellations.providers import get_today
        from leave.cancellations.services import (
            DECISION_APPROVE,
            DECISION_REJECT,
            decide_cancellation,
            submit_cancellation,
        )
        from workflows.services import decide, eligible_approver_ids

        prefix = f"LV-{fy_label}-810"
        if CancellationRequest.objects.filter(
            application__reference_number__startswith=prefix
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Cancellations already seeded (references {prefix}*) — keeping."
                )
            )
            return

        # Deliberately the *second* employee, not employee@test.luanar. Annual
        # leave is a finite per-year balance and the approval scenarios above
        # already finalise leave against the first employee, so sharing one
        # employee between the two groups exhausts the balance partway through
        # and the command fails with INSUFFICIENT_BALANCE — which reads like a
        # routing regression rather than the seed outgrowing its own budget. Two
        # employees, two independent scenario groups.
        employee = User.objects.get(
            username="science-employee@test.luanar", role=User.Role.EMPLOYEE
        )

        today = get_today()

        def approved(seq: int):
            # Each scenario is a fortnight later than the last, and
            # _suitable_start keeps them off weekends, holidays, and anything
            # this employee already has.
            start = self._suitable_start(
                employee, seq, min_offset_days=21 + (seq - 1) * 14
            )
            application = LeaveApplication.objects.create(
                employee=employee,
                leave_type_id=1,
                start_date=start,
                end_date=start + timedelta(days=6),
                reason=f"Cancellation scenario {seq} (seeded)",
                reference_number=f"{prefix}{seq:03d}",
            )
            submitted = submit_application(
                user=employee, application_id=application.pk
            )
            # Walk the application's own chain rather than a hardcoded list of
            # approvers. The chain is now a property of the employee's team, so
            # naming the roles here would re-introduce exactly the hardcoding
            # this feature removes — and would break the moment HR reorders a
            # workflow, with a "not_current_stage" error that reads like a
            # routing bug.
            #
            # Each step is decided by whoever is entitled to act, read from the
            # stage's eligibility snapshot. ``assigned_approver`` is null until
            # somebody claims the stage, so it is never a valid actor here.
            for _ in range(len(SEED_TEAMS) + len(SEED_ROLES)):
                stage = submitted.current_stage
                if stage is None:
                    break
                eligible = eligible_approver_ids(submitted, stage)
                if not eligible:
                    raise CommandError(
                        f"No eligible approver for stage {stage.stage_order} of "
                        f"{submitted.reference_number} — check the section's "
                        "membership in HR → Teams."
                    )
                submitted = decide(
                    application_id=submitted.pk,
                    actor=User.objects.get(pk=eligible[0]),
                    action="approve",
                    comment="",
                    expected_version=stage.decision_version,
                )
                if submitted.status == LeaveApplication.Status.APPROVED:
                    break
            return submitted

        def request_for(seq: int, reason: str):
            return submit_cancellation(
                user=employee,
                application_id=approved(seq).pk,
                reason=reason,
                confirm=True,
                expected_action="request",
                today=today,
            )

        def decide_request(request, decision: str, comment: str = ""):
            """Decide whichever cancellation stage is currently pending.

            The cancellation chain is derived from the application's own
            workflow snapshot — the stages whose role handles cancellations — so
            its length and order depend on the employee's team. Naming roles here
            would hardcode the very configuration this feature moves into data, and
            would raise ``NotCurrentApproverError`` as soon as a team is
            reconfigured.
            """
            stage = (
                CancellationApprovalStage.objects.filter(
                    request=request,
                    status=CancellationApprovalStage.Status.PENDING,
                )
                .prefetch_related("eligible_approvers")
                .order_by("order")
                .first()
            )
            if stage is None:
                return request
            return decide_cancellation(
                user=User.objects.get(pk=stage.eligible_approver_ids()[0]),
                request_id=request.pk,
                decision=decision,
                comment=comment,
                stage_version=request.stage_version,
                today=today,
            )

        def decide_all(request, decision: str, comment: str = ""):
            for _ in range(len(SEED_ROLES)):
                request = decide_request(request, decision, comment)
                if request.status != CancellationRequest.Status.PENDING:
                    break
            return request

        # Pending at the first cancellation approver.
        request_for(
            1,
            "A departmental retreat prevents me taking the approved leave as planned.",
        )

        # Pending at the second cancellation approver (first already approved).
        decide_all(
            request_for(
                2, "An audit deadline now conflicts with the approved leave dates."
            ),
            DECISION_APPROVE,
        )

        # Fully cancelled: approved through every cancellation stage, balance
        # restored.
        decide_all(
            request_for(
                3, "The project I was heading was postponed until next year."
            ),
            DECISION_APPROVE,
            "Leave recovery approved.",
        )

        # Rejected: the leave stays approved but appears in the decided tab.
        decide_all(
            request_for(
                4, "I have been asked to travel for an overseas workshop."
            ),
            DECISION_REJECT,
            "Coverage cannot be spared over this period.",
        )

        self.stdout.write(
            self.style.SUCCESS(f"Done. Seeded cancellations with references {prefix}*.")
        )

    def _seed_documents(self, fy_label: str):
        """Unit 19 document-lifecycle scenarios (references LV-<FY>-820NNN).

        Attaches supporting documents directly (no Supabase uploads) so the
        employee uploader, archive and tracking card have realistic content:
        a ``correction_required`` application with one active row plus one
        retired``/``replaced`` row (exercises the replace UI and archive), and
        a draft with two active rows. Idempotent on the 820 prefix.
        """
        from leave.models import SupportingDocument

        prefix = f"LV-{fy_label}-820"
        if LeaveApplication.objects.filter(
            reference_number__startswith=prefix
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Documents already seeded (references {prefix}*) — keeping."
                )
            )
            return

        employee = User.objects.get(
            username="employee@test.luanar", role=User.Role.EMPLOYEE
        )

        def add(application, name, content_type="application/pdf", size=48_000):
            return SupportingDocument.objects.create(
                application=application,
                file_path=f"seeded/820/{application.reference_number}/{name}",
                file_url=(
                    f"https://dev-storage/leave-documents/"
                    f"{application.reference_number}/{name}"
                ),
                file_name=name,
                file_size=size,
                content_type=content_type,
            )

        start = self._suitable_start(employee, 8)

        corrected = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=start,
            end_date=start + timedelta(days=6),
            reason="Document replacement scenario (seeded)",
            reference_number=f"{prefix}01",
            status=LeaveApplication.Status.CORRECTION_REQUIRED,
        )
        active = add(corrected, "leave-letter.pdf")
        replaced = add(corrected, "medical-certificate-v1.pdf")
        replaced.retire(
            employee,
            reason=SupportingDocument.RetireReason.REPLACED,
            replaced_by=active,
        )

        draft = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=1,
            start_date=start + timedelta(days=21),
            end_date=start + timedelta(days=27),
            reason="Draft with documents (seeded)",
            reference_number=f"{prefix}02",
            status=LeaveApplication.Status.DRAFT,
        )
        add(draft, "annual-certificate.pdf")
        add(draft, "supporting-note.txt", content_type="text/plain")

        self.stdout.write(
            self.style.SUCCESS(f"Done. Seeded documents with references {prefix}*.")
        )