"""Dev seed for the Unit 16 approver dashboard (DEBUG-only).

Creates submitted leave applications that flow through the live workflow so the
approver dashboard has realistic pending/decided items for every approver role.
Scenario chain used by the fixture workflow provider:

* ``employee@test.luanar`` (Administration) → supervisor → hod → registrar → dvc
* ``employee@test.luanar`` (separate account outside the dean's faculty) is
  created for the Dean's review-scope boundary; a Mathematics academic maps to
  hod → dean → registrar → dvc.

Idempotent: once a scenario reference (``LV-<FY>-800NNN``) exists, the command
keeps the existing applications untouched. Requires ``seed_dev_users`` first.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leave.models import LeaveApplication
from leave.services.submission import submit_application
from users.models import EmployeeProfile, User

FIYEAR_PREFIX = "800"
DEV_PASSWORD = "testpass123"


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
        fy_label = fy.label if fy else None
        if not fy_label:
            raise CommandError("No active financial year configured.")

        self._ensure_second_employee()

        prefix = f"LV-{fy_label}-{FIYEAR_PREFIX}"
        if LeaveApplication.objects.filter(
            reference_number__startswith=prefix
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Approvals already seeded (references {prefix}*) — keeping."
                )
            )
            return

        self._seed_applications(fy_label, prefix)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created approvals with references {prefix}*."
            )
        )

    def _ensure_second_employee(self):
        """An academic outside the Dean's faculty (review-scope boundary)."""
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
        pending_supervisor = act(submit(app(employee, 1, "Annual")))
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

    def _suitable_start(self, user, seq: int) -> date:
        """A working day giving >= 5 working days' notice from today."""
        today = timezone.localdate()
        candidate = today
        count = 0
        while True:
            candidate += timedelta(days=1)
            if candidate.weekday() >= 5:
                continue
            count += 1
            if count >= 6 + (seq % 2):  # stagger scenarios a little
                return candidate