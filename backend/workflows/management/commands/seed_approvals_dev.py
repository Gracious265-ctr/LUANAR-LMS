"""Seed fixture approval data for Unit 16 (idempotent dev/demo command).

Reuses the seeded ``@test.luanar`` users (creating per-approver-role ones when
missing) and builds pending/rejected/correction-required/fully-approved
applications through the real Unit 14 submit service and Unit 16 decide service,
so every stage/decision row is consistent with production code. One application
demos the "requested exceeds available balance" read-only note and one carries a
supporting document (real storage when Supabase env vars are present, otherwise
metadata only).

Idempotent: an application that already carries one of the reserved reference
numbers is left untouched; approver/employee users are found-or-created.
"""

from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from leave.models import LeaveApplication, LeaveType, ReferenceSequence
from leave.services.references import next_reference
from leave.services.storage import upload_document
from workflows import fixture_provider as workflow_fixture
from workflows.approval import decide
from workflows.policies import get_view_access

User = get_user_model()

FINANCIAL_YEAR_LABEL = "2026-27"
FIRST_RESERVED_SUFFIX = 910001
SEQUENCE_TARGET = 910000

APPROVER_DEFS = [
    ("supervisor", "Computer Science", "academic", "E", "2018-09-01"),
    ("hod", "Computer Science", "academic", "G", "2015-01-10"),
    ("dean", "Applied Sciences", "academic", "H", "2012-06-01"),
    ("registrar", "Registry", "administration", "H", "2010-08-15"),
    ("dvc", "Executive", "administration", "H", "2008-04-01"),
]

# (scenario key, employee username, leave type name, start, end, advance)
# ``advance`` is None (leave pending), "role1,role2" (approve through those
# roles), "reject@role", or "return@role".
#
# ``exceeds_available_balance`` runs first so the employee's working-day
# balance is untouched at submit (22 requested days <= grade-B 24-day balance),
# then the grade is downgraded so the review payload shows a read-only
# "requested > available" note.
SCENARIOS = [
    ("exceeds_available_balance", "employee@test.luanar", "Annual", "2027-01-04", "2027-02-02", None),
    ("pending_at_hod", "employee@test.luanar", "Annual", "2026-11-02", "2026-11-06", None),
    ("pending_at_dean", "employee@test.luanar", "Annual", "2026-11-09", "2026-11-13", "hod"),
    ("pending_at_registrar", "employee@test.luanar", "Annual", "2026-11-16", "2026-11-20", "hod,dean"),
    ("pending_at_dvc", "employee@test.luanar", "Annual", "2026-11-23", "2026-11-27", "hod,dean,registrar"),
    ("pending_at_supervisor", "academic@test.luanar", "Annual", "2026-11-30", "2026-12-04", None),
    ("rejected_at_hod", "employee@test.luanar", "Annual", "2026-12-07", "2026-12-11", "reject@hod"),
    ("correction_required_at_hod", "employee@test.luanar", "Annual", "2026-12-14", "2026-12-18", "return@hod"),
    ("fully_approved", "employee@test.luanar", "Annual", "2026-12-21", "2026-12-25", "hod,dean,registrar,dvc"),
    ("with_document", "employee@test.luanar", "Compassionate", "2026-12-28", "2026-12-29", "hod"),
]

DOCUMENT_NAME = "return-to-work-certificate.pdf"


class Command(BaseCommand):
    help = (
        "Seed Unit 16 approval scenarios (references LV-2026-27-910001..). "
        "Idempotent; requires no special flags."
    )

    def handle(self, *args, **options):
        approvers = {
            role: self._user_for_role(role, username, department, category, grade, appointed)
            for role, username, department, category, grade, appointed in self._approver_rows()
        }
        employees = {
            "employee@test.luanar": self._employee(
                "employee@test.luanar", "Registry", "administration", "B", "2022-03-15"
            ),
            "academic@test.luanar": self._employee(
                "academic@test.luanar", "Computer Science", "academic", "E", "2018-09-01"
            ),
        }
        self.approvers = approvers

        self._ensure_workflow_fixture_map()
        visible = {role: [] for role in approvers}
        with transaction.atomic():
            self._fast_forward_sequence_if_needed()
            for slot, (key, emp_username, leave_name, start, end, advance) in enumerate(SCENARIOS):
                reference = self._scenario(slot, employees[emp_username], key, leave_name, start, end, advance)
                for role, user in approvers.items():
                    app = LeaveApplication.objects.filter(reference_number=reference).first()
                    if app is not None and get_view_access(user, app) is not None:
                        visible[role].append(reference)

        self._print_summary(approvers, visible)
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            self.stdout.write(
                self.style.WARNING(
                    "Supabase storage is not configured: documents were seeded "
                    "with metadata only; downloads will 503 until storage is set up."
                )
            )

    def _approver_rows(self):
        return [
            (role, f"{role}@test.luanar", department, category, grade, appointed)
            for role, department, category, grade, appointed in APPROVER_DEFS
        ]

    def _user_for_role(self, role, username, department, category, grade, appointed):
        user = User.objects.filter(role=role, is_active=True).order_by("username").first()
        if user is None:
            user = User.objects.create_user(
                username=username, email=username, password="testpass123", role=role
            )
        self._ensure_profile(user, department, category, grade, appointed)
        return user

    def _employee(self, username, department, category, grade, appointed):
        user, _ = User.objects.get_or_create(
            username=username, defaults={"email": username, "role": User.Role.EMPLOYEE}
        )
        self._ensure_profile(user, department, category, grade, appointed)
        return user

    def _ensure_profile(self, user, department, category, grade, appointed):
        from users.models import EmployeeProfile

        profile = getattr(user, "employee_profile", None)
        if profile is not None:
            return profile
        return EmployeeProfile.objects.create(
            user=user,
            designation=department,
            department=department,
            category=category,
            grade=grade,
            appointment_date=date.fromisoformat(appointed),
        )

    def _ensure_workflow_fixture_map(self):
        defaults = workflow_fixture.FIXTURE_WORKFLOWS
        defaults.setdefault(("academic", ""), ("supervisor", "hod", "registrar", "dvc"))
        defaults.setdefault(("administration", ""), ("hod", "dean", "registrar", "dvc"))

    def _fast_forward_sequence_if_needed(self):
        existing = self._existing_references().count()
        if existing >= len(SCENARIOS):
            return
        seq, _ = ReferenceSequence.objects.select_for_update().get_or_create(
            financial_year_label=FINANCIAL_YEAR_LABEL,
            defaults={"last_value": SEQUENCE_TARGET},
        )
        if seq.last_value < SEQUENCE_TARGET:
            seq.last_value = SEQUENCE_TARGET
            seq.save(update_fields=["last_value"])

    def _existing_references(self):
        return LeaveApplication.objects.filter(
            reference_number__startswith=f"LV-{FINANCIAL_YEAR_LABEL}-{FIRST_RESERVED_SUFFIX}"
        )

    def reserved_ref(self, slot: int) -> str:
        return f"LV-{FINANCIAL_YEAR_LABEL}-{FIRST_RESERVED_SUFFIX + slot:06d}"

    def _scenario(self, slot, employee, key, leave_name, start, end, advance):
        expected = self.reserved_ref(slot)
        existing = LeaveApplication.objects.filter(reference_number=expected).first()
        if existing is not None:
            self.stdout.write(self.style.WARNING(f"Exists, kept: {key}: {expected}"))
            return expected

        if key == "exceeds_available_balance":
            self._upgrade_to_allow_submit(employee)
        app = self._submit(employee, leave_name, start, end)
        # The submit service assigns the authoritative reference via
        # next_reference(); reference_number (and its sequence value) are
        # authoritative, so the read-back below is the single source of truth.
        ref = app.reference_number
        self.stdout.write(
            self.style.SUCCESS(f"Created {key}: {ref} ({leave_name.lower()} leave)")
        )
        self._advance(app, key, advance)
        if key == "exceeds_available_balance":
            self._downgrade_to_exceed_balance(employee)
        if key == "with_document":
            self._attach_document(app, ref)
        return ref

    def _submit(self, employee, leave_name, start, end):
        leave_type_id = self._leave_type_id(leave_name)
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=leave_type_id,
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end),
            reason=f"Seed approval scenario {employee.username}",
        )
        from leave.services.submission import submit_application

        try:
            submit_application(user=employee, application_id=app.id)
        except Exception as exc:
            details = ""
            if exc.__class__.__name__ == "ValidationFailedError":
                details = "; ".join(
                    f"{issue.field}:{issue.message}"
                    for issue in getattr(exc, "errors", ())
                )
            raise RuntimeError(
                f"Seed scenario failed at submit for {employee.username} "
                f"({leave_name}, {start}..{end}): {details or exc}"
            ) from exc
        app.refresh_from_db()
        return app

    def _leave_type_id(self, leave_name):
        from leave.providers import fixture_data as leave_fixture_data

        for rules in leave_fixture_data.LEAVE_TYPES:
            if rules.name.lower() == leave_name.lower() or leave_name.lower() in rules.name.lower():
                return rules.id
        leave_type = LeaveType.objects.filter(name__icontains=leave_name).first()
        return leave_type.id if leave_type else None

    def _advance(self, app, key, advance):
        if not advance:
            return
        if advance.startswith("reject@"):
            role = advance.split("@")[1]
            self._decide(app, self.approvers[role], "reject", "Insufficient staffing in the period.")
            return
        if advance.startswith("return@"):
            role = advance.split("@")[1]
            self._decide(app, self.approvers[role], "return_for_correction", "Please correct the reason.")
            return
        for role in advance.split(","):
            self._decide(app, self.approvers[role], "approve", "Approved.")

    def _decide(self, app, actor, action, comment):
        stage = app.current_stage
        decide(
            application_id=app.id,
            actor=actor,
            action=action,
            comment=comment,
            expected_stage_version=stage.version,
        )
        app.refresh_from_db()

    def _upgrade_to_allow_submit(self, employee):
        # Grade D sits in band D-G (24 days), letting the 22-working-day request
        # pass the available-balance gate at submit. It is downgraded right
        # after (to grade A, 21 days) so the review payload shows a read-only
        # "requested > available" note.
        profile = employee.employee_profile
        if profile is not None:
            profile.grade = "D"
            profile.save(update_fields=["grade"])

    def _downgrade_to_exceed_balance(self, employee):
        # Grade D (24 days) let the 22-working-day request submit; dropping to
        # grade A (21 days) makes the balance note show "requested > available"
        # without blocking the original submission.
        profile = employee.employee_profile
        if profile is not None:
            profile.grade = "A"
            profile.save(update_fields=["grade"])

    def _attach_document(self, app, reference):
        from leave.models import SupportingDocument

        file_path = f"leave-documents/{app.id}/{DOCUMENT_NAME}"
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            try:
                file_path = upload_document(
                    SimpleUploadedFile(
                        DOCUMENT_NAME,
                        b"%PDF-1.4 seed approval certificate",
                        content_type="application/pdf",
                    ),
                    str(app.id),
                )["path"]
            except Exception as exc:  # noqa: BLE001 - storage failures degrade to metadata
                self.stdout.write(
                    self.style.WARNING(f"Storage upload failed ({exc}); metadata only.")
                )
        SupportingDocument.objects.create(
            application=app,
            file_path=file_path,
            file_url=f"https://cdn.example.test/{file_path}",
            file_name=DOCUMENT_NAME,
            file_size=1024,
            content_type="application/pdf",
        )

    def _print_summary(self, approvers, visible):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seeded approval data"))
        self.stdout.write("=====================")
        self.stdout.write(f"{'Role':<14}{'Username':<28}{'Visible applications'}")
        for role, user in approvers.items():
            refs = ", ".join(visible[role]) or "(none)"
            self.stdout.write(f"{role:<14}{user.username:<28}{refs}")