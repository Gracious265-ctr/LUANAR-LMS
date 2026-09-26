"""Seed fixture approval data for Units 16-18 (idempotent dev/demo command).

Reuses the seeded ``@test.luanar`` users (creating per-approver-role ones when
missing) and builds pending/rejected/correction-required/fully-approved
applications through the real Unit 14 submit service and Unit 16 decide service,
so every stage/decision row is consistent with production code. Unit 17
scenarios additionally exercise the real resubmission services (in-place edit
keeping the terminal status, resubmission back to the same approver, and
replaced/added documents) so the demo data mirrors production behaviour. One
application demos the "requested exceeds available balance" read-only note and
one carries a supporting document (real storage when Supabase env vars are
present, otherwise metadata only).

Unit 18 adds a cancellation block (section 3.10) with dates relative to today:
a pending application at stage 2, approved annual leave with a seeded 5-day
ledger deduction, approved leave starting tomorrow/today/yesterday (blocked
cases), approved maternity leave (no balance impact), a rejected application
(not cancellable), and one approved academic application carrying an open
cancellation request at stage 1 of 2 (pending with the seeded Supervisor).

Idempotent: an application that already carries one of the reserved reference
numbers is left untouched; approver/employee users are found-or-created.
"""

from datetime import date, timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from leave import defaults as leave_defaults
from leave.models import LeaveApplication, LeaveType, ReferenceSequence
from leave.services.references import next_reference
from leave.storage import get_storage_backend
from workflows import fixture_provider as workflow_fixture
from workflows.approval import decide
from workflows.policies import get_view_access

User = get_user_model()

FINANCIAL_YEAR_LABEL = "2026-27"
FIRST_RESERVED_SUFFIX = 910001
SEQUENCE_TARGET = 910000

APPROVER_DEFS = [
    ("supervisor", "Computer Science", "academic", "E", "2018-09-01", "M"),
    ("hod", "Computer Science", "academic", "G", "2015-01-10", "M"),
    ("dean", "Applied Sciences", "academic", "H", "2012-06-01", "M"),
    ("registrar", "Registry", "administration", "H", "2010-08-15", "F"),
    ("dvc", "Executive", "administration", "H", "2008-04-01", "F"),
]

# (scenario key, employee username, leave type name, start, end, advance)
# ``advance`` is None (leave pending), "role1,role2" (approve through those
# roles), "reject@role", "return@role", or any of those suffixed with ",edit"
# (the employee then edits the content in place, keeping the terminal status)
# or ",resubmit" (the employee edits and resubmits back to the same approver).
#
# ``exceeds_available_balance`` runs first so the employee's working-day
# balance is untouched at submit (22 requested days <= grade-B 24-day balance),
# then the grade is downgraded so the review payload shows a read-only
# "requested > available" note. The Unit 17 scenarios run against
# ``academic@test.luanar`` (first stage: supervisor) on non-overlapping 2027
# windows so the resubmit full-pipeline re-validation passes.
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
    ("rejected_then_edited", "academic@test.luanar", "Annual", "2027-02-08", "2027-02-12", "reject@supervisor,edit"),
    ("resubmitted_after_rejection", "academic@test.luanar", "Annual", "2027-02-15", "2027-02-19", "reject@supervisor,resubmit"),
    ("correction_then_edited", "academic@test.luanar", "Annual", "2027-02-22", "2027-02-26", "return@supervisor,edit"),
    ("returned_then_resubmitted", "academic@test.luanar", "Annual", "2027-03-01", "2027-03-05", "return@supervisor,resubmit"),
    ("rejected_with_replaced_document", "academic@test.luanar", "Compassionate", "2027-03-08", "2027-03-12", "reject@supervisor"),
]

DOCUMENT_NAME = "return-to-work-certificate.pdf"
REPLACEMENT_DOCUMENT_NAME = "updated-return-to-work-certificate.pdf"
ADDITIONAL_DOCUMENT_NAME = "hospital-note.pdf"


class Command(BaseCommand):
    help = (
        "Seed Unit 16/17 approval scenarios (references LV-2026-27-910001..). "
        "Idempotent; requires no special flags."
    )

    def handle(self, *args, **options):
        leave_defaults.ensure_default_entitlements()
        leave_defaults.ensure_default_leave_types_and_rules()
        leave_defaults.ensure_default_financial_year()

        approvers = {
            role: self._user_for_role(role, username, department, category, grade, appointed, gender)
            for role, username, department, category, grade, appointed, gender in self._approver_rows()
        }
        employees = {
            "employee@test.luanar": self._employee(
                "employee@test.luanar", "Registry", "administration", "B", "2022-03-15", "F"
            ),
            "academic@test.luanar": self._employee(
                "academic@test.luanar", "Computer Science", "academic", "E", "2018-09-01", "M"
            ),
        }
        self.approvers = approvers

        self._ensure_workflow_fixture_map()
        visible = {role: [] for role in approvers}
        self.cancellation_scenarios = self._cancellation_scenarios()
        scenarios = SCENARIOS + self.cancellation_scenarios
        with transaction.atomic():
            self._fast_forward_sequence_if_needed()
            for slot, (key, emp_username, leave_name, start, end, advance) in enumerate(scenarios):
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
            (role, f"{role}@test.luanar", department, category, grade, appointed, gender)
            for role, department, category, grade, appointed, gender in APPROVER_DEFS
        ]

    def _user_for_role(self, role, username, department, category, grade, appointed, gender):
        user = User.objects.filter(role=role, is_active=True).order_by("username").first()
        if user is None:
            user = User.objects.create_user(
                username=username, email=username, password="testpass123", role=role
            )
        self._ensure_profile(user, department, category, grade, appointed, gender)
        return user

    def _employee(self, username, department, category, grade, appointed, gender):
        user, _ = User.objects.get_or_create(
            username=username, defaults={"email": username, "role": User.Role.EMPLOYEE}
        )
        self._ensure_profile(user, department, category, grade, appointed, gender)
        return user

    def _ensure_profile(self, user, department, category, grade, appointed, gender):
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
            gender=gender,
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
        app = self._submit(
            employee,
            leave_name,
            start,
            end,
            attach_document=(key == "cancellation_approved_maternity"),
        )
        # The submit service assigns the authoritative reference via
        # next_reference(); reference_number (and its sequence value) are
        # authoritative, so the read-back below is the single source of truth.
        ref = app.reference_number
        self.stdout.write(
            self.style.SUCCESS(f"Created {key}: {ref} ({leave_name.lower()} leave)")
        )
        self._advance(app, key, advance, employee)
        if key == "exceeds_available_balance":
            self._downgrade_to_exceed_balance(employee)
        if key == "with_document":
            self._attach_document(app, ref)
        if key == "rejected_with_replaced_document":
            self._attach_document(app, ref)
            self._replace_and_add_documents(app)
        self._cancellation_post_step(key, app, employee)
        return ref

    def _cancellation_scenarios(self):
        """Unit 18 block (section 3.10): dates relative to today so they rotate.

        Windows are kept mutually non-overlapping (the submit service rejects
        overlapping leave for the same employee), ordered so each scenario
        submits against already-finalized earlier ones. Annual leave needs 5
        working days notice, so the tomorrow/today/yesterday demos submit with
        a future window and are then backdated by ``_cancellation_post_step``
        — the start-date guard is what the demo exercises.

        A window that would open on a weekend is pushed to the next working
        day (the submit service rejects a weekend start) and nudged past any
        window already claimed for the same employee, so overlapping windows
        never reach the submit call whichever weekday today is. The
        ``today + 14`` (approved-14d) and ``today + 12`` (academic-10d) windows
        are asserted verbatim by ``workflows/tests_seed_cancellations.py`` and
        are returned exactly as computed on a working-day anchor; when the
        anchor itself is a weekend (Saturday/Sunday), they too shift to the
        next working day so the seed never breaks — the test asserts the same
        shifted dates.
        """
        from leave.validation.working_days import is_weekend

        today = timezone.localdate()
        pinned = {
            ("employee@test.luanar", 14): today + timedelta(days=14),
            ("academic@test.luanar", 12): today + timedelta(days=12),
        }
        claimed = {}

        def starts(offset_days, width_days=4, employee="employee@test.luanar"):
            start = today + timedelta(days=offset_days)
            claimed_for = claimed.setdefault(employee, [])
            if (employee, offset_days) in pinned:
                if is_weekend(start):
                    while is_weekend(start):
                        start += timedelta(days=1)
                end = start + timedelta(days=width_days)
                claimed_for.append((start, end))
                return start.isoformat(), end.isoformat()
            while is_weekend(start) or any(start <= end for _, end in claimed_for):
                start += timedelta(days=1)
            end = start + timedelta(days=width_days)
            claimed_for.append((start, end))
            return start.isoformat(), end.isoformat()

        return [
            # Employee A — administration workflow (hod -> dean -> registrar -> dvc).
            ("cancellation_pending_at_stage2", "employee@test.luanar", "Annual", *starts(21), "hod"),
            ("cancellation_approved_14d", "employee@test.luanar", "Annual", *starts(14), "hod,dean,registrar,dvc"),
            ("cancellation_approved_tomorrow", "employee@test.luanar", "Annual", *starts(8, 0), "hod,dean,registrar,dvc"),
            ("cancellation_approved_today", "employee@test.luanar", "Annual", *starts(12, 0), "hod,dean,registrar,dvc"),
            ("cancellation_approved_yesterday", "employee@test.luanar", "Annual", *starts(11, 0), "hod,dean,registrar,dvc"),
            ("cancellation_approved_maternity", "employee@test.luanar", "Maternity", *starts(200), "hod,dean,registrar,dvc"),
            ("cancellation_rejected_app", "employee@test.luanar", "Annual", *starts(33, 0), "reject@hod"),
            # Employee B — academic workflow (supervisor -> hod -> registrar -> dvc).
            ("cancellation_academic_10d", "academic@test.luanar", "Annual", *starts(12, employee="academic@test.luanar"), "supervisor,hod,registrar,dvc"),
        ]

    def _cancellation_post_step(self, key, app, employee):
        from leave.models import LeaveBalanceTransaction

        if key == "cancellation_approved_14d":
            self._seed_deduction(app, LeaveBalanceTransaction.Type.DEDUCTION, "5")
        elif key == "cancellation_approved_tomorrow":
            self._seed_deduction(app, LeaveBalanceTransaction.Type.DEDUCTION, "5")
            self._backdate_start(app, timezone.localdate() + timedelta(days=1))
        elif key == "cancellation_approved_today":
            self._seed_deduction(app, LeaveBalanceTransaction.Type.DEDUCTION, "5")
            self._backdate_start(app, timezone.localdate())
        elif key == "cancellation_approved_yesterday":
            self._seed_deduction(app, LeaveBalanceTransaction.Type.DEDUCTION, "5")
            self._backdate_start(app, timezone.localdate() - timedelta(days=1))
        elif key == "cancellation_academic_10d":
            self._seed_deduction(app, LeaveBalanceTransaction.Type.DEDUCTION, "5")
            self._open_cancellation_request(app, employee)
        # Maternity and rejected scenarios intentionally add no ledger row and no
        # open request (maternity restores 0, a rejected app is not cancellable).

    def _seed_deduction(self, app, txn_type, days):
        """Create one ledger row for an approved leave (section 3.3 fixtures)."""
        from leave.models import LeaveBalanceTransaction

        LeaveBalanceTransaction.objects.get_or_create(
            employee=app.employee,
            application=app,
            leave_type_id=app.leave_type_id,
            financial_year=FINANCIAL_YEAR_LABEL,
            type=txn_type,
            defaults={
                "days": days,
                "carry_forward_eligible": False,
            },
        )

    def _backdate_start(self, app, target):
        """Shift an approved application so it starts on ``target``.

        The whole window moves by the same delta (single-day demos stay single
        day), so the range never sweeps across other seeded windows.
        """
        delta = target - app.start_date
        app.start_date = target
        if app.end_date is not None:
            app.end_date = app.end_date + delta
        app.save(update_fields=["start_date", "end_date"])
        app.refresh_from_db()

    def _open_cancellation_request(self, app, employee):
        from leave.cancellations.services import submit_cancellation

        submit_cancellation(
            user=employee,
            application_id=app.id,
            reason="Seed demo: requesting cancellation of approved leave.",
            confirm=True,
            expected_action="request",
        )

    def _submit(self, employee, leave_name, start, end, attach_document=False):
        leave_type_id = self._leave_type_id(leave_name)
        app = LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=leave_type_id,
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end),
            reason=f"Seed approval scenario {employee.username}",
        )
        if attach_document:
            self._attach_document(app, self.reserved_ref(0), metadata_only=True)
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
        leave_type = LeaveType.objects.filter(name__icontains=leave_name).first()
        return leave_type.id if leave_type else None

    def _advance(self, app, key, advance, employee):
        if not advance:
            return
        edit_after = advance.endswith(",edit") or advance.endswith(",resubmit")
        resubmit_after = advance.endswith(",resubmit")
        action_part = advance.replace(",edit", "").replace(",resubmit", "")
        if action_part.startswith("reject@"):
            role = action_part.split("@")[1]
            self._decide(app, self.approvers[role], "reject", "Insufficient staffing in the period.")
        elif action_part.startswith("return@"):
            role = action_part.split("@")[1]
            self._decide(app, self.approvers[role], "return_for_correction", "Please correct the reason.")
        else:
            for role in action_part.split(","):
                self._decide(app, self.approvers[role], "approve", "Approved.")
        if edit_after:
            self._edit_in_place(app, employee)
        if resubmit_after:
            self._resubmit_in_place(app, employee)

    def _edit_in_place(self, app, employee):
        from leave.services.resubmission import save_changes

        app.refresh_from_db()
        save_changes(
            application_id=app.id,
            actor=employee,
            leave_type_id=app.leave_type_id,
            start_date=app.start_date,
            end_date=app.end_date,
            reason=f"{app.reason} — amended after {app.status}.",
            expected_row_version=app.row_version,
        )
        app.refresh_from_db()

    def _resubmit_in_place(self, app, employee):
        from leave.services.resubmission import resubmit

        app.refresh_from_db()
        resubmit(
            application_id=app.id,
            actor=employee,
            expected_row_version=app.row_version,
        )
        app.refresh_from_db()

    def _replace_and_add_documents(self, app):
        from leave.models import SupportingDocument
        from leave.services.resubmission import add_document, replace_document

        original = app.documents.filter(
            status=SupportingDocument.Status.ACTIVE
        ).first()
        if original is None:
            return
        replace_document(
            application_id=app.id,
            actor=app.employee,
            document_id=original.id,
            file=SimpleUploadedFile(
                REPLACEMENT_DOCUMENT_NAME,
                b"%PDF-1.4 superseded certificate",
                content_type="application/pdf",
            ),
            expected_row_version=app.row_version,
        )
        app.refresh_from_db()
        add_document(
            application_id=app.id,
            actor=app.employee,
            file=SimpleUploadedFile(
                ADDITIONAL_DOCUMENT_NAME,
                b"%PDF-1.4 hospital note",
                content_type="application/pdf",
            ),
            expected_row_version=app.row_version,
        )
        app.refresh_from_db()

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

    def _attach_document(self, app, reference, metadata_only=False):
        from leave.models import SupportingDocument

        document_id = uuid4()
        file_path = f"leave-documents/{app.id}/{document_id}/{DOCUMENT_NAME}"
        if (
            not metadata_only
            and settings.SUPABASE_URL
            and settings.SUPABASE_SERVICE_KEY
        ):
            try:
                get_storage_backend().put(
                    path=file_path,
                    file_obj=SimpleUploadedFile(
                        DOCUMENT_NAME,
                        b"%PDF-1.4 seed approval certificate",
                        content_type="application/pdf",
                    ),
                    content_type="application/pdf",
                )
            except Exception as exc:  # noqa: BLE001 - storage failures degrade to metadata
                self.stdout.write(
                    self.style.WARNING(f"Storage upload failed ({exc}); metadata only.")
                )
        SupportingDocument.objects.create(
            id=document_id,
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