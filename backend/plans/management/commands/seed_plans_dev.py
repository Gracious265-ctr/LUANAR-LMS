"""Dev seed for the Unit 26 leave day plans (DEBUG-only).

Walks real plans through the real services so the plans dashboard has realistic
content in every lifecycle state. One employee per state (each employee has at
most one open plan per financial year, D1):

* ``plan-employee@test.luanar`` — approved plan whose near block is confirmed
  (inside the confirmation window) and whose far block is reserved but not yet
  confirmable.
* ``peer-employee@test.luanar`` — approved block overlapping the first
  employee's confirmed block in the same department/grade (peer-conflict pair).
* ``draft-employee@test.luanar`` — draft plan (blocks proposed, nothing
  reserved).
* ``submit-employee@test.luanar`` — submitted plan parked at the supervisor.
* ``hod-employee@test.luanar`` — submitted plan parked at the HOD.
* ``reject-employee@test.luanar`` — rejected plan (reason recorded).

Plan users are dedicated so their annual balance is unused and their blocks
never collide with the leave applications seeded for ``employee@test.luanar``
by ``seed_approvals_dev``. The supervisor stage is pinned via
``EmployeeProfile.supervisor`` (D20); approval chains come from the real
``Workflow`` rows (seeded by ``seed_approvals_dev`` when missing).

Idempotent: once any plan exists for the active financial year, existing plans
are kept. Requires ``seed_dev_users`` first.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leave.models import LeaveType
from leave.services.working_days import holidays_in_range
from plans.models import LeaveDayPlan
from plans.services import confirm_block, create_plan, decide_plan, submit_plan
from users.models import EmployeeProfile, User

DEV_PASSWORD = "testpass123"


class Command(BaseCommand):
    help = (
        "Seed leave day plans across their lifecycle for the plans dashboard "
        "(Unit 26). Requires DEBUG=true and seed_dev_users first."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_plans_dev only runs with DEBUG=true.")

        from users.management.commands.seed_dev_users import (
            Command as SeedUsersCommand,
        )

        SeedUsersCommand().handle()

        self._seed_workflows()

        fy = self._active_financial_year()
        fy_label = fy["label"]
        period_start, period_end = fy["period"]
        today = timezone.localdate()
        holidays = holidays_in_range(today + timedelta(days=1), today + timedelta(days=90))

        if LeaveDayPlan.objects.filter(financial_year_label=fy_label).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Plans already seeded for FY {fy_label} — keeping existing plans."
                )
            )
            return

        annual = LeaveType.objects.get(code="annual")
        supervisor = User.objects.get(username="supervisor@test.luanar")
        hod = User.objects.get(username="hod@test.luanar")
        registrar = User.objects.get(username="registrar@test.luanar")
        dvc = User.objects.get(username="dvc@test.luanar")

        def working_day(offset: int) -> date:
            """The n-th working day from tomorrow (skips weekends/holidays)."""
            candidate = today
            count = 0
            while True:
                candidate += timedelta(days=1)
                if candidate.weekday() >= 5 or candidate in holidays:
                    continue
                count += 1
                if count >= offset:
                    return candidate

        def act(plan, user, action, comment=""):
            stage = plan.current_stage
            return decide_plan(
                plan_id=plan.pk,
                actor=user,
                action=action,
                comment=comment,
                expected_version=stage.decision_version,
            )

        def approve_fully(plan):
            for actor in (supervisor, hod, registrar, dvc):
                plan = act(plan, actor, "approve")
            return plan

        with transaction.atomic():
            # Approved plan: the near block sits inside the confirmation window
            # (reminder-worthy and shown in the "confirm now" queue), the middle
            # block is already confirmed (days locked), and the far block is
            # reserved but not yet confirmable.
            near_start = working_day(8)
            mid_start = working_day(14)
            far_start = working_day(30)
            employee = self._employee(
                "plan-employee@test.luanar", "Mapopa", "Nyirenda", supervision=supervisor
            )
            approved = self._plan(
                employee,
                annual,
                fy_label,
                period_start,
                period_end,
                [
                    (near_start, near_start + timedelta(days=1)),
                    (mid_start, mid_start + timedelta(days=1)),
                    (far_start, far_start + timedelta(days=2)),
                ],
            )
            approved = approve_fully(submit_plan(user=employee, plan_id=approved.pk))

            # Peer-conflict pair: same department/grade, overlapping block.
            peer = self._employee(
                "peer-employee@test.luanar",
                "Chimwemwe",
                "Phiri",
                supervision=supervisor,
                template=employee,
            )
            peer_plan = self._plan(
                peer,
                annual,
                fy_label,
                period_start,
                period_end,
                [(near_start, near_start + timedelta(days=1))],
            )
            approve_fully(submit_plan(user=peer, plan_id=peer_plan.pk))

            # Draft.
            draft_user = self._employee(
                "draft-employee@test.luanar", "Thoko", "Mwale", supervision=supervisor
            )
            draft_start = working_day(7)
            self._plan(
                draft_user,
                annual,
                fy_label,
                period_start,
                period_end,
                [(draft_start, draft_start + timedelta(days=2))],
            )

            # Submitted, parked at the supervisor.
            submit_user = self._employee(
                "submit-employee@test.luanar", "Elton", "Chirwa", supervision=supervisor
            )
            submitted_start = working_day(12)
            submitted = self._plan(
                submit_user,
                annual,
                fy_label,
                period_start,
                period_end,
                [(submitted_start, submitted_start + timedelta(days=1))],
            )
            submit_plan(user=submit_user, plan_id=submitted.pk)

            # Submitted, parked at the HOD.
            hod_user = self._employee(
                "hod-employee@test.luanar", "Tamanda", "Banda", supervision=supervisor
            )
            hod_start = working_day(17)
            hod_plan = self._plan(
                hod_user,
                annual,
                fy_label,
                period_start,
                period_end,
                [(hod_start, hod_start + timedelta(days=3))],
            )
            hod_plan = submit_plan(user=hod_user, plan_id=hod_plan.pk)
            act(hod_plan, supervisor, "approve")

            # Rejected (recorded, shows in the decided tab).
            reject_user = self._employee(
                "reject-employee@test.luanar", "Grace", "Kalonga", supervision=supervisor
            )
            rejected_start = working_day(22)
            rejected = self._plan(
                reject_user,
                annual,
                fy_label,
                period_start,
                period_end,
                [(rejected_start, rejected_start + timedelta(days=1))],
            )
            rejected = submit_plan(user=reject_user, plan_id=rejected.pk)
            act(rejected, supervisor, "approve")
            act(
                rejected,
                hod,
                "reject",
                comment="Roofing contractor overlaps the department's year-end stock take.",
            )

        confirm_block(
            plan_id=approved.pk,
            block_id=approved.plan_blocks.filter(start_date=mid_start).first().pk,
            user=employee,
        )
        confirm_block(
            plan_id=peer_plan.pk,
            block_id=peer_plan.plan_blocks.filter(start_date=near_start).first().pk,
            user=peer,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Done. Seeded leave day plans across draft/submitted/approved/"
                "rejected states, a confirmation-window plan and a peer-conflict "
                "pair."
            )
        )

    def _active_financial_year(self):
        from leave.services import active_financial_year

        fy = active_financial_year()
        if fy is None:
            raise CommandError("No active financial year configured.")
        return {
            "label": f"{fy.start_date.year}-{str(fy.end_date.year)[-2:]}",
            "period": (fy.start_date, fy.end_date),
        }

    def _seed_workflows(self):
        """Reuse the real workflow seeding from the approvals seed."""
        from workflows.management.commands.seed_approvals_dev import (
            Command as SeedApprovalsCommand,
        )

        SeedApprovalsCommand()._seed_workflows()

    def _employee(
        self,
        username: str,
        first_name: str,
        last_name: str,
        supervision: User,
        template: User | None = None,
    ) -> User:
        """Upsert an administration employee pinned to ``supervision``."""
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": username,
                "first_name": first_name,
                "last_name": last_name,
                "role": User.Role.EMPLOYEE,
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()
        template = template or User.objects.get(username="employee@test.luanar")
        source = EmployeeProfile.objects.get(user=template)
        EmployeeProfile.objects.update_or_create(
            user=user,
            defaults={
                "designation": source.designation,
                "department": source.department,
                "grade": source.grade,
                "category": source.category,
                "appointment_date": source.appointment_date,
                "supervisor": supervision,
            },
        )
        return user

    def _plan(
        self,
        user: User,
        annual: LeaveType,
        fy_label: str,
        period_start: date,
        period_end: date,
        blocks: list[tuple[date, date]],
    ) -> LeaveDayPlan:
        return create_plan(
            user=user,
            period_start=period_start,
            period_end=period_end,
            blocks=[
                {"leave_type_id": annual.pk, "start_date": start, "end_date": end}
                for start, end in blocks
            ],
        )