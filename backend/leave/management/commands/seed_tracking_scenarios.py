"""Seed the eight Unit 15 tracking scenarios for the dev employee (Unit 15).

Creates one submitted ``LeaveApplication`` per tracking scenario for the seeded
``employee@test.luanar`` user, using the Unit 14 reference generator to reserve
references ``LV-2026-27-900001``..``900008`` (matching the checked-in
``leave/tracking/fixtures/assignments.json``), then rewrites that mapping file
so the fixture-based tracking provider serves the right scenario per reference.

Idempotent: applications that already carry one of the reserved reference
numbers are left untouched. Refuses to run unless ``settings.DEBUG`` is true
(it is a dev/demo seeding tool).
"""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leave.models import LeaveApplication, LeaveType, ReferenceSequence
from leave.services.references import next_reference

User = get_user_model()

DEV_EMPLOYEE_USERNAME = "employee@test.luanar"
FINANCIAL_YEAR_LABEL = "2026-27"

# (scenario_name, leave_type name, start_date, end_date)
SCENARIOS = [
    ("pending_first_stage", "Annual", "2026-11-02", "2026-11-06"),
    ("pending_mid_workflow", "Annual", "2026-11-09", "2026-11-13"),
    ("pending_with_delegate", "Compassionate", "2026-11-02", "2026-11-03"),
    ("approved", "Annual", "2026-12-07", "2026-12-18"),
    ("rejected_at_stage_2", "Annual", "2026-11-23", "2026-11-27"),
    ("correction_required_at_stage_3", "Paternity", "2026-11-16", "2026-11-20"),
    ("resubmitted_after_correction", "Paternity", "2026-11-16", "2026-11-20"),
    ("resubmitted_after_rejection", "Annual", "2026-11-30", "2026-12-04"),
]

FIRST_RESERVED_SUFFIX = 900001
SEQUENCE_TARGET = 900000

ASSIGNMENTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "leave"
    / "tracking"
    / "fixtures"
    / "assignments.json"
)


class Command(BaseCommand):
    help = (
        "Seed the eight Unit 15 tracking scenarios for the dev employee "
        "(references LV-2026-27-900001..900008). Requires DEBUG=true."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_tracking_scenarios only runs with DEBUG=true.")

        employee = User.objects.filter(
            username=DEV_EMPLOYEE_USERNAME, role=User.Role.EMPLOYEE
        ).first()
        if employee is None:
            raise CommandError(
                f"Dev employee '{DEV_EMPLOYEE_USERNAME}' not found; run "
                "`python manage.py seed_dev_users` first."
            )

        self._seed(employee)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(SCENARIOS)} submitted scenario applications for "
                f"{employee.username}; assignments.json rewritten."
            )
        )

    def _seed(self, employee):
        existing_refs = set(
            LeaveApplication.objects.filter(
                employee=employee,
                reference_number__startswith=f"LV-{FINANCIAL_YEAR_LABEL}-900",
            ).values_list("reference_number", flat=True)
        )

        if len(existing_refs) < len(SCENARIOS):
            self._fast_forward_sequence()

        assignments = {}
        allocated_count = 0
        for slot, (scenario, leave_name, start, end) in enumerate(SCENARIOS):
            expected_ref = self.reserved_ref(slot)
            if expected_ref in existing_refs:
                reference = expected_ref
                self.stdout.write(
                    self.style.WARNING(f"Exists, kept: {scenario}: {reference}")
                )
            else:
                reference = next_reference(FINANCIAL_YEAR_LABEL)
                self._create_application(
                    employee=employee,
                    reference=reference,
                    leave_name=leave_name,
                    start=start,
                    end=end,
                )
                allocated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {scenario}: {reference} "
                        f"({leave_name.lower()} leave)"
                    )
                )
            assignments[reference] = scenario

        self._write_assignments(assignments)
        if allocated_count:
            self.stdout.write(
                self.style.SUCCESS(f"Created {allocated_count} new application(s).")
            )

    def reserved_ref(self, slot: int) -> str:
        """The reference expected to hold scenario ``slot`` (+1 digit digits)."""
        return f"LV-{FINANCIAL_YEAR_LABEL}-{FIRST_RESERVED_SUFFIX + slot:06d}"

    def _create_application(self, *, employee, reference, leave_name, start, end):
        leave_type = LeaveType.objects.filter(name__icontains=leave_name).first()
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        working_days = (end_date - start_date).days + 1
        submitted_at = timezone.now() - timezone.timedelta(days=1)
        return LeaveApplication.objects.create(
            employee=employee,
            leave_type_id=leave_type.id if leave_type else None,
            start_date=start_date,
            end_date=end_date,
            calculated_days=working_days,
            reason=f"Seed scenario {reference}",
            status=LeaveApplication.Status.SUBMITTED,
            reference_number=reference,
            submitted_at=submitted_at,
            working_days=working_days,
            calendar_days=working_days,
            financial_year_label=FINANCIAL_YEAR_LABEL,
            rules_snapshot={
                "leave_type": {
                    "id": leave_type.id if leave_type else None,
                    "name": leave_type.name if leave_type else leave_name,
                }
            },
        )

    def _fast_forward_sequence(self):
        with transaction.atomic():
            seq, _ = ReferenceSequence.objects.select_for_update().get_or_create(
                financial_year_label=FINANCIAL_YEAR_LABEL,
                defaults={"last_value": SEQUENCE_TARGET},
            )
            if seq.last_value < SEQUENCE_TARGET:
                seq.last_value = SEQUENCE_TARGET
                seq.save(update_fields=["last_value"])

    def _write_assignments(self, assignments):
        ordered = dict(
            sorted(
                assignments.items(),
                key=lambda item: int(item[0].rsplit("-", 1)[1]),
            )
        )
        ASSIGNMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ASSIGNMENTS_PATH.write_text(
            json.dumps(ordered, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )