"""Leave day plan domain logic (Unit 25).

Covers the plan lifecycle end to end:

* **submit** — validates every block through the leave-validation pipeline
  (balance incl. reserved days, duration, eligibility, financial year), checks
  the plan's *aggregate* annual-deducting days against the available balance,
  resolves the approval chain from the workflow provider (supervisor stage =
  the employee's assigned supervisor) and parks the plan at its first stage.
* **decide** — approves/rejects the plan through its ``PlanApprovalStage``
  chain; the final approval *reserves* each annual-deducting block's working
  days via the append-only reservation ledger (D8/D9).
* **confirm / release / lapse** — the employee confirms a reserved block inside
  its confirmation window (locking the days), or releases it; an unconfirmed
  block auto-lapses at its start date and the days are returned.

Peer conflicts are **warnings, never blockers** (D5): a plan that overlaps a
peer's published block may still be submitted; the warning is surfaced to the
employee and on the team page so they decide for themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.providers import get_today
from leave.validation.types import ValidationIssue

from .models import (
    LeaveDayPlan,
    LeavePlanBlock,
    PlanApprovalDecision,
    PlanApprovalStage,
    PlanBalanceTransaction,
    get_plan_settings,
)


class PlanNotFoundError(Exception):
    """The plan does not exist or is not owned by the caller."""


class PlanStateError(Exception):
    """The plan is not in the state required by the operation."""


class PlanNotSubmittableError(Exception):
    """The plan is not in ``draft`` status and cannot be submitted."""


class PlanValidationFailedError(Exception):
    """Block validation failed; carries the full error list."""

    def __init__(self, errors, warnings=None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__(f"{len(errors)} validation error(s)")


class PlanDecisionValidationError(ValueError):
    """Invalid approve/reject payload; carries a dict of field errors."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


class PlanDecisionNotAllowedError(Exception):
    """The actor may not decide right now; carries a reason code."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class PlanStageChangedError(Exception):
    """The stage was already decided by someone else (stale/conflict, 409)."""


class BlockStateError(Exception):
    """A plan block cannot be confirmed or released in its current state."""


@dataclass(frozen=True)
class FieldIssue:
    """One block-level validation problem projected for the API."""

    field: str
    code: str
    message: str
    block: int | None = None


def _provider() -> _RulesProvider:
    from leave.providers import get_provider

    return get_provider()


def _plan_blocks(plan: LeaveDayPlan):
    return list(plan.plan_blocks.order_by("start_date", "end_date"))


class PlanBlockInputError(ValueError):
    """A block specification failed basic sanity checks."""


def create_plan(*, user, period_start: date, period_end: date, blocks: list[dict]):
    """Create a draft plan with its blocks (no validation runs yet).

    Enforces the one-open-plan-per-employee-per-FY policy at creation time; the
    DB partial unique constraint pins it again at submit. Raises ``ValueError``
    with a human message for open-plan / bad-period / unknown-leave-type cases.
    """
    if period_end < period_start:
        raise ValueError("The plan period must start before it ends.")
    if not blocks:
        raise ValueError("Add at least one leave block to the plan.")

    provider = _provider()
    fy = provider.get_financial_year_for(period_start)
    if fy is None:
        raise ValueError("The plan period does not fall inside any financial year.")
    if provider.get_financial_year_for(period_end) is None or (
        provider.get_financial_year_for(period_end).label != fy.label
    ):
        raise ValueError("The plan period must sit inside a single financial year.")

    open_plan = LeaveDayPlan.objects.filter(
        employee=user,
        status__in=(
            LeaveDayPlan.Status.DRAFT,
            LeaveDayPlan.Status.SUBMITTED,
            LeaveDayPlan.Status.APPROVED,
        ),
        financial_year_label=fy.label,
    ).exists()
    if open_plan:
        raise ValueError(
            "You already have an open leave day plan for this financial year."
        )

    from leave.models import LeaveType

    # Validity (active rules on the start date) is resolved by the provider at
    # submission; creation only confirms the registry entry exists.
    leave_types = {lt.pk: lt for lt in LeaveType.objects.all()}

    with transaction.atomic():
        plan = LeaveDayPlan.objects.create(
            employee=user,
            period_start=period_start,
            period_end=period_end,
            financial_year_label=fy.label,
            status=LeaveDayPlan.Status.DRAFT,
        )
        plan_rows = []
        for spec in blocks:
            leave_type_id = spec.get("leave_type_id")
            leave_type = leave_types.get(leave_type_id)
            if leave_type is None:
                raise PlanBlockInputError(f"Unknown leave type id {leave_type_id!r}.")
            start = spec["start_date"]
            end = spec["end_date"]
            if end < start:
                raise PlanBlockInputError(
                    f"Block {start} to {end} ends before it starts."
                )
            plan_rows.append(
                LeavePlanBlock(
                    plan=plan,
                    leave_type_id=leave_type.id,
                    start_date=start,
                    end_date=end,
                    status=LeavePlanBlock.Status.PROPOSED,
                    working_days=None,
                )
            )
        LeavePlanBlock.objects.bulk_create(plan_rows)
    return plan


def _annual_deducting(plan: LeaveDayPlan, block) -> bool:
    """Whether the block's leave type deducts annual entitlement (D9)."""
    rules = _provider().get_leave_type_rules(block.leave_type_id, get_today())
    return bool(rules is not None and rules.deducts_annual_balance)


def peer_conflicts(plan: LeaveDayPlan) -> list[dict]:
    """Published peer blocks overlapping ``plan``'s blocks (warnings only).

    Peers are employees with the same free-text department and grade as the
    plan's owner (D2/D14). Only *approved* plans' current/future reserved or
    confirmed blocks are visible to peers; drafts, submitted, rejected,
    cancelled and lapsed blocks never conflict. A block never conflicts with
    its own owner's plan.
    """
    from users.models import EmployeeProfile, User

    profile = getattr(plan.employee, "employee_profile", None)
    if profile is None:
        return []
    department = (profile.department or "").strip()
    grade = (profile.grade or "").strip()
    today = get_today()
    if not department and not grade:
        return []

    peers = EmployeeProfile.objects.filter(
        user__is_active=True,
    )
    if department:
        peers = peers.filter(department__iexact=department)
    if grade:
        peers = peers.filter(grade__iexact=grade)
    peer_ids = list(peers.exclude(user_id=plan.employee_id).values_list("user_id", flat=True))
    if not peer_ids:
        return []

    conflicts: list[dict] = []
    blocks = [b for b in _plan_blocks(plan) if b.end_date >= today]
    publishable = LeavePlanBlock.objects.filter(
        plan__employee_id__in=peer_ids,
        plan__status=LeaveDayPlan.Status.APPROVED,
        end_date__gte=today,
        status__in=(LeavePlanBlock.Status.RESERVED, LeavePlanBlock.Status.CONFIRMED),
    ).select_related("plan__employee")

    for block in blocks:
        for other in publishable:
            if block.end_date < other.start_date or other.end_date < block.start_date:
                continue
            peer_profile = getattr(other.plan.employee, "employee_profile", None)
            conflicts.append(
                {
                    "peer_name": other.plan.employee.get_full_name(),
                    "peer_department": (peer_profile.department if peer_profile else "") or "",
                    "leave_type_id": other.leave_type_id,
                    "start_date": other.start_date.isoformat(),
                    "end_date": other.end_date.isoformat(),
                    "overlaps_start": max(block.start_date, other.start_date).isoformat(),
                    "overlaps_end": min(block.end_date, other.end_date).isoformat(),
                }
            )
    return conflicts


class PlanValidator:
    """Runs the shared leave-validation pipeline per block (D16)."""

    def __init__(self, plan: LeaveDayPlan):
        self.plan = plan
        self.errors: list[FieldIssue] = []
        self.warnings: list[dict] = []

    def validate(self) -> bool:
        from leave.validation.pipeline import run_validation

        blocks = _plan_blocks(self.plan)
        if not blocks:
            self.errors.append(
                FieldIssue(
                    field="blocks",
                    code="NO_PLAN_BLOCKS",
                    message="Add at least one leave block to the plan.",
                )
            )
            return False

        today = get_today()
        provider = _provider()

        start_fy = provider.get_financial_year_for(self.plan.period_start)
        end_fy = provider.get_financial_year_for(self.plan.period_end)
        plan_fy = start_fy
        if start_fy is None or end_fy is None or start_fy.label != end_fy.label:
            self.errors.append(
                FieldIssue(
                    field="period_end",
                    code="PLAN_CROSSES_FINANCIAL_YEAR",
                    message=(
                        "The plan period must sit inside a single financial year."
                    ),
                )
            )
            return False

        self.plan.financial_year_label = plan_fy.label

        total_annual_days = Decimal(0)
        has_annual = False
        for index, block in enumerate(blocks):
            result = run_validation(
                user=self.plan.employee,
                leave_type_id=block.leave_type_id,
                start_date_raw=block.start_date,
                end_date_raw=block.end_date,
                today=today,
            )
            if not result.valid:
                for issue in result.errors:
                    self.errors.append(
                        FieldIssue(
                            field=_block_field(issue.field, block),
                            code=issue.code,
                            message=issue.message,
                            block=index,
                        )
                    )
            block.working_days = result.working_days
            if _annual_deducting_block(block, result):
                has_annual = True
                total_annual_days += Decimal(result.working_days or 0)

        if has_annual:
            available = provider.get_available_balance(
                self.plan.employee_id, plan_fy.label
            )
            if total_annual_days > available:
                self.errors.append(
                    FieldIssue(
                        field="blocks",
                        code="INSUFFICIENT_PLAN_BALANCE",
                        message=(
                            f"The plan totals {int(total_annual_days)} working days, "
                            f"which exceeds your available balance of "
                            f"{int(available)} days."
                        ),
                    )
                )

        if blocks:
            LeavePlanBlock.objects.bulk_update(blocks, ["working_days"])

        self.warnings = peer_conflicts(self.plan)
        return not self.errors


def _annual_deducting_block(block, result) -> bool:
    rules = result.context.leave_type if result.context else None
    return bool(rules is not None and rules.deducts_annual_balance)


def _block_field(field: str, block) -> str:
    prefix = f"block[{block.start_date.isoformat()}]"
    if field in ("start_date", "end_date"):
        return f"{prefix}.{field}"
    return prefix


def check_plan_workflow_ready(plan: LeaveDayPlan) -> None:
    """Resolve the plan's approval chain, raising a list of ``FieldIssue``s."""
    from workflows.providers import WorkflowConfigError, get_workflow_provider

    try:
        definitions = get_workflow_provider().get_stage_definitions(plan)
    except WorkflowConfigError as exc:
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message=str(exc),
                )
            ]
        )
    if not definitions:
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message="No approval workflow is configured for this plan.",
                )
            ]
        )
    missing = [
        f"No active approver for the {definition.role_label} stage."
        for definition in definitions
        if definition.approver_user_id is None
    ]
    if missing:
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message=f"{message}",
                )
                for message in missing
            ]
        )


def assign_plan_workflow(plan: LeaveDayPlan) -> PlanApprovalStage:
    """Materialise the plan's approval chain (mirrors ``assign_workflow``).

    Reuses the workflow provider's stage definitions (so the supervisor stage
    resolves to the employee's assigned supervisor, D20/D21) and the shared
    self-approval skip policy: a stage whose approver is the employee is
    materialised ``skipped`` and the first stage with a different approver is
    activated.
    """
    from workflows.providers import WorkflowConfigError, get_workflow_provider
    from workflows.services import SelfApprovalBlockedError

    try:
        definitions = get_workflow_provider().get_stage_definitions(plan)
    except WorkflowConfigError as exc:
        raise PlanValidationFailedError(
            [FieldIssue(field="—", code="workflow_unavailable", message=str(exc))]
        )

    if not definitions or sorted(d.order for d in definitions) != list(
        range(1, len(definitions) + 1)
    ):
        raise PlanValidationFailedError(
            [FieldIssue(field="—", code="workflow_unavailable", message="Workflow stages must be ordered 1..N.")]
        )

    from workflows.services import select_activatable_stage_index

    try:
        active_index = select_activatable_stage_index(plan, definitions)
    except SelfApprovalBlockedError as exc:
        raise PlanValidationFailedError(
            [FieldIssue(field="—", code="workflow_unavailable", message=message) for message in exc.messages]
        )

    from users.models import User

    from workflows.models import STAGE_ROLE_LABELS

    stages = []
    for index, definition in enumerate(definitions):
        approver = User.objects.filter(pk=definition.approver_user_id).first()
        if approver is None:
            raise PlanValidationFailedError(
                [
                    FieldIssue(
                        field="—",
                        code="workflow_unavailable",
                        message=f"No active user for the {definition.role_label} stage.",
                    )
                ]
            )
        status = (
            PlanApprovalStage.Status.SKIPPED
            if index < active_index
            else (
                PlanApprovalStage.Status.PENDING
                if index == active_index
                else PlanApprovalStage.Status.WAITING
            )
        )
        stages.append(
            PlanApprovalStage(
                plan=plan,
                submission_cycle=plan.submission_cycle,
                stage_order=definition.order,
                role=definition.role,
                role_label=definition.role_label
                or STAGE_ROLE_LABELS.get(definition.role, definition.role),
                assigned_approver=approver,
                status=status,
                is_final=index == len(definitions) - 1,
            )
        )

    PlanApprovalStage.objects.bulk_create(stages)
    if plan.approval_stages.filter(status="pending").exists():
        plan.current_stage = stages[active_index]
        plan.current_approver = stages[active_index].assigned_approver
        plan.save(update_fields=["current_stage", "current_approver", "updated_at"])
    return stages[active_index]


def submit_plan(*, user, plan_id):
    """Validate a draft plan and route it into the approval chain.

    Raises ``PlanNotFoundError`` (404), ``PlanNotSubmittableError`` (409) or
    ``PlanValidationFailedError`` (422). Returns the persisted plan on success.
    """
    plan = (
        LeaveDayPlan.objects.select_for_update()
        .filter(id=plan_id, employee=user)
        .first()
    )
    if plan is None:
        raise PlanNotFoundError()
    if plan.status != LeaveDayPlan.Status.DRAFT:
        raise PlanNotSubmittableError()

    validator = PlanValidator(plan)
    if not validator.validate():
        raise PlanValidationFailedError(validator.errors, validator.warnings)

    check_plan_workflow_ready(plan)

    plan.status = LeaveDayPlan.Status.SUBMITTED
    plan.submitted_at = timezone.now()
    plan.save(update_fields=["status", "submitted_at", "updated_at"])

    active_stage = assign_plan_workflow(plan)

    record_audit(
        actor=user,
        action=AuditEntry.Action.PLAN_SUBMITTED,
        target_type=AuditEntry.TargetType.PLAN,
        target_id=plan.pk,
        target_summary=str(plan),
        detail=changed_fields(
            {"status": LeaveDayPlan.Status.DRAFT},
            {
                "status": LeaveDayPlan.Status.SUBMITTED,
                "financial_year": plan.financial_year_label,
                "current_approver_id": active_stage.assigned_approver_id,
            },
        ),
    )

    from notifications.plans import notify_plan_assigned

    notify_plan_assigned(plan.pk)

    return plan


def acting_approver_id(plan) -> int | None:
    """The user entitled to act on a pending plan right now.

    Mirrors ``workflows.services.acting_approver_id`` but scoped to
    ``PlanApprovalStage`` rows; single-level delegation applies unchanged.
    """
    from workflows.services import _active_delegation_for_id

    responsible_id = plan.current_approver_id
    if responsible_id is None and plan.current_stage_id is not None:
        responsible_id = (
            PlanApprovalStage.objects.filter(pk=plan.current_stage_id)
            .values_list("assigned_approver_id", flat=True)
            .first()
        )
    if responsible_id is None:
        return None
    delegation = _active_delegation_for_id(responsible_id)
    if delegation is not None and delegation.delegate_id is not None:
        return delegation.delegate_id
    return responsible_id


def _lock_plan_and_stage(plan_id, actor):
    plan = LeaveDayPlan.objects.select_for_update().filter(id=plan_id).first()
    if plan is None:
        raise PlanNotFoundError()
    if plan.current_stage_id is None:
        raise PlanDecisionNotAllowedError("plan_closed")
    stage = (
        PlanApprovalStage.objects.select_for_update()
        .filter(pk=plan.current_stage_id)
        .first()
    )
    if stage is None or stage.submission_cycle != plan.submission_cycle:
        raise PlanDecisionNotAllowedError("plan_closed")
    return plan, stage


def decide_plan(
    *,
    plan_id,
    actor,
    action: str,
    comment: str = "",
    expected_version: int,
):
    """Record one decision and advance the plan.

    Approve/advance mirrors ``workflows.services.decide`` but is plan-scoped.
    The *final* approval reserves each annual-deducting block (D9). Raises
    ``PlanNotFoundError`` (404), ``PlanDecisionValidationError`` (400),
    ``PlanDecisionNotAllowedError`` (403) or ``PlanStageChangedError`` (409).
    """
    if action not in PlanApprovalDecision.Action.values:
        raise PlanDecisionValidationError(
            {"action": "Must be approve or reject."}
        )
    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise PlanDecisionValidationError(
            {"comment": "Must be at most 1000 characters."}
        )
    if action == PlanApprovalDecision.Action.REJECT and not comment:
        raise PlanDecisionValidationError(
            {"comment": "A comment is required when rejecting a plan."}
        )

    plan = None
    with transaction.atomic():
        plan, stage = _lock_plan_and_stage(plan_id, actor)

        if plan.status not in (LeaveDayPlan.Status.SUBMITTED,):
            raise PlanDecisionNotAllowedError("plan_closed")
        if stage.status != PlanApprovalStage.Status.PENDING:
            raise PlanDecisionNotAllowedError("already_decided")
        if stage.decision_version != expected_version:
            raise PlanStageChangedError()
        if PlanApprovalDecision.objects.filter(
            plan=plan, approver=actor, submission_cycle=plan.submission_cycle
        ).exists():
            raise PlanStageChangedError()
        if (
            plan.employee_id == actor.pk
            or acting_approver_id(plan) != actor.pk
        ):
            raise PlanDecisionNotAllowedError("not_current_stage")

        before_status = plan.status
        before_order = stage.stage_order
        before_version = stage.decision_version

        PlanApprovalDecision.objects.create(
            plan=plan,
            stage=stage,
            approver=actor,
            approver_name=actor.get_full_name(),
            role_label=stage.role_label,
            action=action,
            comment=comment,
            submission_cycle=plan.submission_cycle,
        )

        next_stage = None
        if action == PlanApprovalDecision.Action.APPROVE:
            stage.status = PlanApprovalStage.Status.APPROVED
            if stage.is_final:
                plan.status = LeaveDayPlan.Status.APPROVED
            else:
                next_stage = _next_activatable_stage(plan, stage)
                next_stage.status = PlanApprovalStage.Status.PENDING
        else:
            stage.status = PlanApprovalStage.Status.REJECTED
            plan.status = LeaveDayPlan.Status.REJECTED

        stage.decision_version = before_version + 1
        stage.save(update_fields=["status", "decision_version", "updated_at"])
        if next_stage is not None:
            next_stage.save(update_fields=["status", "updated_at"])
            plan.current_stage = next_stage
            plan.current_approver = next_stage.assigned_approver

        finalised = plan.status == LeaveDayPlan.Status.APPROVED
        if finalised:
            plan.decided_at = timezone.now()
        plan.save(
            update_fields=[
                "status",
                "current_stage",
                "current_approver",
                "decided_at",
                "updated_at",
            ]
        )

        if finalised:
            _reserve_approved_blocks(plan)

        record_audit(
            actor=actor,
            action=(
                AuditEntry.Action.PLAN_APPROVED
                if finalised
                else AuditEntry.Action.PLAN_REJECTED
            ),
            target_type=AuditEntry.TargetType.PLAN,
            target_id=plan.pk,
            target_summary=str(plan),
            detail=changed_fields(
                {
                    "status": before_status,
                    "current_stage_order": before_order,
                    "decision_version": before_version,
                },
                {
                    "status": plan.status,
                    "current_stage_order": (
                        plan.current_stage.stage_order
                        if plan.current_stage_id is not None
                        else stage.stage_order
                    ),
                    "decision_version": stage.decision_version,
                },
            ),
            reason=comment,
        )

        from notifications.plans import notify_plan_decided

        transaction.on_commit(lambda p=plan.pk, s=finalised: notify_plan_decided(p, s))

    return plan


def _next_activatable_stage(plan, decided_stage):
    remaining = list(
        PlanApprovalStage.objects.select_for_update()
        .filter(
            plan=plan,
            submission_cycle=plan.submission_cycle,
            stage_order__gt=decided_stage.stage_order,
        )
        .order_by("stage_order")
    )
    for candidate in remaining:
        if candidate.status == PlanApprovalStage.Status.SKIPPED:
            continue
        return candidate
    raise PlanDecisionValidationError(
        {"action": "Workflow chain is incomplete."}
    )


def _reserve_approved_blocks(plan: LeaveDayPlan) -> None:
    """Write the append-only reservation rows for a finally-approved plan (D8/D9).

    Only annual-deducting blocks reserve capacity. ``working_days`` was frozen
    at submission by the validator; blocks that never ran validation (e.g. all
    validation failed) cannot reach an approved state.
    """
    for block in _plan_blocks(plan):
        if not _annual_deducting(plan, block):
            block.status = LeavePlanBlock.Status.RESERVED
            block.save(update_fields=["status", "updated_at"])
            continue
        PlanBalanceTransaction.objects.create(
            block=block,
            employee_id=plan.employee_id,
            financial_year=plan.financial_year_label,
            leave_type_id=block.leave_type_id,
            type=PlanBalanceTransaction.Type.RESERVE,
            days=Decimal(block.working_days or 0),
        )
        block.status = LeavePlanBlock.Status.RESERVED
        block.save(update_fields=["status", "updated_at"])


def _confirmation_window_start(block) -> date:
    """The day the employee first gets asked to confirm a block."""
    from datetime import timedelta

    lead = get_plan_settings().confirmation_lead_days
    return block.start_date - timedelta(days=lead)


def blocks_awaiting_confirmation(plan: LeaveDayPlan):
    """Reserved, current+future blocks inside their confirmation window."""
    today = get_today()
    return [
        block
        for block in _plan_blocks(plan)
        if block.status == LeavePlanBlock.Status.RESERVED
        and block.end_date >= today
        and _confirmation_window_start(block) <= today < block.start_date
    ]


def confirm_block(plan_id: int, block_id, user) -> LeavePlanBlock:
    """Employee confirms a reserved block inside its confirmation window.

    Writes an informational ``confirm`` ledger row (the reserve row already
    held the capacity) and locks the block for a future leave application.
    """
    plan = LeaveDayPlan.objects.filter(id=plan_id, employee=user).first()
    if plan is None:
        raise PlanNotFoundError()
    block = LeavePlanBlock.objects.filter(id=block_id, plan=plan).first()
    if block is None:
        raise PlanNotFoundError()
    today = get_today()
    if block.status != LeavePlanBlock.Status.RESERVED:
        raise BlockStateError("Only a reserved plan block can be confirmed.")
    if block.start_date <= today:
        # D11: a block whose start date passed without a decision already
        # lapsed; there is nothing left to confirm.
        raise BlockStateError("This block has already started; it can no longer be confirmed.")

    with transaction.atomic():
        PlanBalanceTransaction.objects.create(
            block=block,
            employee_id=plan.employee_id,
            financial_year=plan.financial_year_label,
            leave_type_id=block.leave_type_id,
            type=PlanBalanceTransaction.Type.CONFIRM,
            days=Decimal(block.working_days or 0),
        )
        block.status = LeavePlanBlock.Status.CONFIRMED
        block.confirmed_at = timezone.now()
        block.save(update_fields=["status", "confirmed_at", "updated_at"])

        record_audit(
            actor=user,
            action=AuditEntry.Action.PLAN_CONFIRMED,
            target_type=AuditEntry.TargetType.PLAN,
            target_id=plan.pk,
            target_summary=str(plan),
            detail=changed_fields(
                {"block_id": str(block.id)},
                {
                    "block_id": str(block.id),
                    "status": LeavePlanBlock.Status.CONFIRMED,
                },
            ),
        )

        from notifications.plans import notify_plan_block_confirmed

        transaction.on_commit(
            lambda b=block.pk, p=plan.pk: notify_plan_block_confirmed(b, p)
        )

    return block


def release_block(plan_id: int, block_id, user) -> LeavePlanBlock:
    """Employee or HR releases a reserved block before it starts (D23).

    Frees the reserved capacity immediately via a ``release`` ledger row.
    """
    plan = LeaveDayPlan.objects.filter(id=plan_id).first()
    if plan is None:
        raise PlanNotFoundError()
    block = LeavePlanBlock.objects.filter(id=block_id, plan=plan).first()
    if block is None:
        raise PlanNotFoundError()

    today = get_today()
    if block.status not in (
        LeavePlanBlock.Status.RESERVED,
        LeavePlanBlock.Status.CONFIRMED,
    ):
        raise BlockStateError(
            "Only a reserved or confirmed block can be released before it starts."
        )
    if block.start_date <= today:
        raise BlockStateError(
            "A block that has already started cannot be released; request HR help."
        )

    with transaction.atomic():
        if block.status == LeavePlanBlock.Status.CONFIRMED:
            # A confirmed block already has a confirm row; releasing restores
            # the reserved capacity either way.
            pass
        PlanBalanceTransaction.objects.create(
            block=block,
            employee_id=plan.employee_id,
            financial_year=plan.financial_year_label,
            leave_type_id=block.leave_type_id,
            type=PlanBalanceTransaction.Type.RELEASE,
            days=Decimal(block.working_days or 0),
        )
        block.status = LeavePlanBlock.Status.RELEASED
        block.released_at = timezone.now()
        block.save(update_fields=["status", "released_at", "updated_at"])

        record_audit(
            actor=user,
            action=AuditEntry.Action.PLAN_RELEASED,
            target_type=AuditEntry.TargetType.PLAN,
            target_id=plan.pk,
            target_summary=str(plan),
            detail=changed_fields(
                {"block_id": str(block.id)}, {"block_id": str(block.id)}
            ),
        )

        from notifications.plans import notify_plan_block_released

        transaction.on_commit(
            lambda b=block.pk, p=plan.pk: notify_plan_block_released(b, p)
        )

    return block


def lapse_overdue_blocks(today: date | None = None) -> int:
    """Auto-lapse reserved blocks whose start date has passed (D11).

    Runs periodically (django-q2): an unconfirmed reserved block lapses at its
    start date, freeing the reserved capacity. Returns the number lapsed.
    """
    today = today or get_today()
    overdue = list(
        LeavePlanBlock.objects.filter(
            status=LeavePlanBlock.Status.RESERVED,
            start_date__lt=today,
        ).select_related("plan")
    )
    count = 0
    for block in overdue:
        plan = block.plan
        with transaction.atomic():
            # Only blocks of approved plans carry a reserve row; guard idempotency.
            if block.status != LeavePlanBlock.Status.RESERVED:
                continue
            PlanBalanceTransaction.objects.create(
                block=block,
                employee_id=plan.employee_id,
                financial_year=plan.financial_year_label,
                leave_type_id=block.leave_type_id,
                type=PlanBalanceTransaction.Type.RELEASE,
                days=Decimal(block.working_days or 0),
            )
            block.status = LeavePlanBlock.Status.LAPSED
            block.released_at = timezone.now()
            block.save(update_fields=["status", "released_at", "updated_at"])
            record_audit(
                actor=None,
                action=AuditEntry.Action.PLAN_RELEASED,
                target_type=AuditEntry.TargetType.PLAN,
                target_id=plan.pk,
                target_summary=str(plan),
                detail={"block_id": str(block.id), "reason": "auto_lapse"},
            )
            count += 1
    return count


def reservation_net(employee_id: int, financial_year_label: str) -> Decimal:
    """Reserved minus released days for one employee/year (capacity held)."""
    from django.db.models import Q, Sum

    delta = PlanBalanceTransaction.objects.filter(
        employee_id=employee_id,
        financial_year=financial_year_label,
    ).aggregate(
        reserved=Sum(
            "days",
            filter=Q(type=PlanBalanceTransaction.Type.RESERVE),
        ),
        released=Sum(
            "days",
            filter=Q(type=PlanBalanceTransaction.Type.RELEASE),
        ),
    )
    reserved = delta["reserved"] or Decimal(0)
    released = delta["released"] or Decimal(0)
    return Decimal(reserved) - Decimal(released)