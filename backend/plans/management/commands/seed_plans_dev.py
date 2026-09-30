"""Dev seed for the leave day plans (DEBUG-only).

Walks real plans through the real services so the plans dashboard has realistic
content in every lifecycle state. One employee per state (each employee has at
most one open plan per financial year, D1):

* ``plan-employee@test.luanar`` — approved plan whose middle block is confirmed
  (inside the confirmation window) and whose far block is reserved but not yet
  confirmable.
* ``peer-employee@test.luanar`` — approved block overlapping the first
  employee's block in the *same team* (peer-conflict pair — peers are team
  members now, not profile look-alikes).
* ``draft-employee@test.luanar`` — draft plan (blocks proposed, nothing
  reserved).
* ``submit-employee@test.luanar`` — submitted plan parked at the first section.
* ``hod-employee@test.luanar`` — submitted plan parked at the second section.
* ``reject-employee@test.luanar`` — rejected plan (reason recorded).

Plan users are dedicated so their annual balance is unused and their blocks never
collide with the leave applications seeded for ``employee@test.luanar``. Approval
chains come from the real teams, workflows and sections seeded by
``seed_approvals_dev``: every plan employee is placed on the Administration Team,
and each seeded decision is driven off the live stage's eligibility snapshot
rather than a hardcoded list of approvers — so the seed exercises exactly the
"whoever acts first" rule the production path uses.

Idempotent: once any plan exists for the active financial year, existing plans are
kept. Requires ``seed_dev_users`` first (run for you).
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leave.models import LeaveType
from leave.services.working_days import holidays_in_range
from plans.models import LeaveDayPlan
from plans.services import (
    confirm_block,
    create_plan,
    decide_plan,
    eligible_approver_ids,
    submit_plan,
)
from users.models import EmployeeProfile, User

DEV_PASSWORD = "testpass123"

# Every plan employee sits on this team, so they share an approval chain and see
# each other's approved blocks as peer conflicts.
PLAN_TEAM_CODE = "administration"


class Command(BaseCommand):
    help = (
        "Seed leave day plans across their lifecycle for the plans dashboard. "
        "Requires DEBUG=true; runs seed_dev_users and the approvals team seed "
        "first."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_plans_dev only runs with DEBUG=true.")

        from users.management.commands.seed_dev_users import (
            Command as SeedUsersCommand,
        )

        SeedUsersCommand().handle()

        team = self._seed_teams_and_people()

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

        def next_actor(plan):
            """Whoever the live stage is open to, lowest id first for determinism.

            Read from the eligibility snapshot — the same rows the authorisation
            check consults — so the seed cannot drift from the routing the
            provider actually produced.
            """
            ids = eligible_approver_ids(plan)
            if not ids:
                raise CommandError(
                    f"Plan {plan.pk} has a stage nobody can act on."
                )
            return User.objects.filter(pk=min(ids)).first()

        def approve_fully(plan):
            while plan.status == LeaveDayPlan.Status.SUBMITTED:
                plan = act(plan, next_actor(plan), "approve")
            return plan

        with transaction.atomic():
            # Approved plan: the middle block sits inside the confirmation window
            # (reminder-worthy and shown in the "confirm now" queue), and the far
            # block is reserved but not yet confirmable.
            near_start = working_day(8)
            mid_start = working_day(14)
            far_start = working_day(30)
            employee = self._employee(
                "plan-employee@test.luanar", "Mapopa", "Nyirenda", team=team
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

            # Peer-conflict pair: same team, overlapping block.
            peer = self._employee(
                "peer-employee@test.luanar",
                "Chimwemwe",
                "Phiri",
                team=team,
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
                "draft-employee@test.luanar", "Thoko", "Mwale", team=team
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

            # Submitted, parked at the first section.
            submit_user = self._employee(
                "submit-employee@test.luanar", "Elton", "Chirwa", team=team
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

            # Submitted, parked at the second section.
            second_user = self._employee(
                "hod-employee@test.luanar", "Tamanda", "Banda", team=team
            )
            second_start = working_day(17)
            second_plan = self._plan(
                second_user,
                annual,
                fy_label,
                period_start,
                period_end,
                [(second_start, second_start + timedelta(days=3))],
            )
            second_plan = submit_plan(user=second_user, plan_id=second_plan.pk)
            act(second_plan, next_actor(second_plan), "approve")

            # Rejected at the second section (recorded, shows in the decided tab).
            reject_user = self._employee(
                "reject-employee@test.luanar", "Grace", "Kalonga", team=team
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
            rejected = act(rejected, next_actor(rejected), "approve")
            act(
                rejected,
                next_actor(rejected),
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
                f"pair, all routed through the '{team.name}' team chain."
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

    def _seed_teams_and_people(self):
        """Seed the real roles/campuses/workflows/teams, then return our team.

        Delegates to the approvals seed's configuration pass — roles, campuses,
        chains, teams, section members and the institution-wide registrar — so
        plans route through exactly the configuration an administrator would have
        built, rather than a private chain that exists only for this seed.
        """
        from workflows.management.commands.seed_approvals_dev import (
            Command as SeedApprovalsCommand,
        )

        SeedApprovalsCommand().handle()

        from workflows.models import Team

        team = Team.objects.filter(code=PLAN_TEAM_CODE).first()
        if team is None:
            raise CommandError(
                f"The approvals seed did not create a '{PLAN_TEAM_CODE}' team."
            )
        return team

    def _employee(
        self,
        username: str,
        first_name: str,
        last_name: str,
        team,
        template: User | None = None,
    ) -> User:
        """Upsert an administration employee placed on ``team``.

        ``team`` is what selects the employee's approval chain, so it is the only
        routing input this seed needs — the person no longer carries a supervisor
        pointer at all.
        """
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
                "team": team,
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
