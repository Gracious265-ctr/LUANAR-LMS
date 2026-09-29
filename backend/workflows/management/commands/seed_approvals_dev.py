"""Dev seed for the Unit 16 approver dashboard (DEBUG-only).

Creates submitted leave applications that flow through the live workflow so the
approver dashboard has realistic pending/decided items for every approver role.
The chain comes from the real ``Workflow``/``WorkflowStage`` rows seeded by
``_seed_workflows`` (Unit 21):

* Administration (employee@test.luanar) → supervisor → hod → registrar → dvc
* Academic (the separate ``science-employee@test.luanar`` outside the dean's
  faculty) → hod → dean → registrar → dvc.

Idempotent: once a scenario reference (``LV-<FY>-800NNN``) exists, the command
keeps the existing applications untouched. Requires ``seed_dev_users`` first.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.utils import timezone

from leave.models import LeaveApplication
from leave.services.submission import submit_application
from leave.services.working_days import holidays_in_range
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
        fy_label = (
            f"{fy.start_date.year}-{str(fy.end_date.year)[-2:]}" if fy else None
        )
        if not fy_label:
            raise CommandError("No active financial year configured.")

        self._ensure_second_employee()
        self._seed_workflows()

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

    def _seed_workflows(self):
        """Real ``Workflow``/``WorkflowStage`` rows (Unit 21).

        Idempotent by workflow name; ``effective_from`` defaults to the active
        financial year's start so the ``DatabaseWorkflowProvider`` treats the
        chains as live configuration from day one.
        """
        from workflows.models import Workflow, WorkflowStage

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
        for name, category, roles in definitions:
            workflow, created = Workflow.objects.get_or_create(
                name=name,
                defaults={
                    "employee_category": category,
                    "effective_from": effective,
                    "is_active": True,
                },
            )
            if created:
                WorkflowStage.objects.bulk_create(
                    [
                        WorkflowStage(
                            workflow=workflow,
                            order=index,
                            approver_role=role,
                        )
                        for index, role in enumerate(roles, start=1)
                    ]
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Seeded workflow '{name}'.")
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

    def _suitable_start(self, user, seq: int) -> date:
        """A working day giving >= 5 working days' notice from today.

        Scenarios are staggered 8 working days apart (>= 5 days' notice and
        > 7 calendar days between starts) so the seeded 7-day application spans
        never overlap for the same employee, which the validation pipeline
        would otherwise reject. Public holidays are skipped as well as
        weekends, so a seeded application never starts on a day validation
        rejects.
        """
        today = timezone.localdate()
        holidays = holidays_in_range(today + timedelta(days=1), today + timedelta(days=60))
        candidate = today
        count = 0
        target = 5 + 8 * (seq - 1)
        while True:
            candidate += timedelta(days=1)
            if candidate.weekday() >= 5 or candidate in holidays:
                continue
            count += 1
            if count >= target:  # stagger scenarios a little
                return candidate

    def _seed_cancellations(self, fy_label: str):
        """Unit 18 cancellation scenarios (references LV-<FY>-810NNN).

        Creates approved applications that actually flowed through the real
        workflow, then opens/rejects/approves cancellation requests so the
        supervisor queue and decided tab have realistic items. Idempotent on
        the 810 prefix.
        """
        from leave.cancellations.models import CancellationRequest
        from leave.cancellations.providers import get_today
        from leave.cancellations.services import (
            DECISION_APPROVE,
            DECISION_REJECT,
            decide_cancellation,
            submit_cancellation,
        )
        from workflows.services import decide

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

        employee = User.objects.get(
            username="employee@test.luanar", role=User.Role.EMPLOYEE
        )
        supervisor = User.objects.get(username="supervisor@test.luanar")
        hod = User.objects.get(username="hod@test.luanar")
        registrar = User.objects.get(username="registrar@test.luanar")
        dvc = User.objects.get(username="dvc@test.luanar")

        today = get_today()
        latest_end = LeaveApplication.objects.filter(
            employee=employee
        ).aggregate(max=models.Max("end_date"))["max"]
        base_start = (
            max(latest_end + timedelta(days=1), today + timedelta(days=21))
            if latest_end
            else today + timedelta(days=21)
        )
        while base_start.weekday() >= 5:
            base_start += timedelta(days=1)

        def approved(seq: int):
            start = base_start + timedelta(days=(seq - 1) * 14)
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
            for actor in (supervisor, hod, registrar, dvc):
                stage = submitted.current_stage
                submitted = decide(
                    application_id=submitted.pk,
                    actor=actor,
                    action="approve",
                    comment="",
                    expected_version=stage.decision_version,
                )
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

        # Pending at the supervisor (first cancellation approver).
        request_for(
            1,
            "A departmental retreat prevents me taking the approved leave as planned.",
        )

        # Pending at the HOD (supervisor already approved).
        hod_request = request_for(
            2, "An audit deadline now conflicts with the approved leave dates."
        )
        decide_cancellation(
            user=supervisor,
            request_id=hod_request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=today,
        )

        # Fully cancelled: approved through both stages, balance restored.
        cancelled_request = request_for(
            3, "The project I was heading was postponed until next year."
        )
        decide_cancellation(
            user=supervisor,
            request_id=cancelled_request.pk,
            decision=DECISION_APPROVE,
            comment="",
            stage_version=1,
            today=today,
        )
        decide_cancellation(
            user=hod,
            request_id=cancelled_request.pk,
            decision=DECISION_APPROVE,
            comment="Leave recovery approved.",
            stage_version=2,
            today=today,
        )

        # Rejected: the leave stays approved but appears in the decided tab.
        rejected_request = request_for(
            4, "I have been asked to travel for an overseas workshop."
        )
        decide_cancellation(
            user=supervisor,
            request_id=rejected_request.pk,
            decision=DECISION_REJECT,
            comment="Coverage cannot be spared over this period.",
            stage_version=1,
            today=today,
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