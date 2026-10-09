"""Leave day plan domain logic (Unit 25).

Covers the plan lifecycle end to end:

* **submit** — validates every block through the leave-validation pipeline
  (balance incl. reserved days, duration, eligibility, financial year), checks
  the plan's *aggregate* annual-deducting days against the available balance,
  resolves the approval chain from the workflow provider (the employee's *team*
  selects the workflow, and every active section of it becomes one stage) and
  parks the plan at its first stage.
* **decide** — approves/rejects the plan through its ``PlanApprovalStage``
  chain; the final approval *reserves* each annual-deducting block's working
  days via the append-only reservation ledger (D8/D9).
* **confirm / release / lapse** — the employee confirms a reserved block inside
  its confirmation window (locking the days), or releases it; an unconfirmed
  block auto-lapses at its start date and the days are returned.

The plan approval chain is a plan-scoped mirror of the leave application's: a
section is resolved by **whoever acts first** out of the eligibility snapshot
the provider produced, so ``PlanApprovalStage`` holds a *set* of candidates
(``PlanApprovalStageApprover``) rather than one pre-assigned approver, and no
stage is ever skipped — see :func:`assign_plan_workflow`.

Peer conflicts are **warnings, never blockers** (D5): a plan that overlaps a
peer's published block may still be submitted; the warning is surfaced to the
employee and on the team page so they decide for themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
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
    PlanApprovalStageApprover,
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

    Peers are the other active members of the plan owner's *team* (D2/D14) —
    the same grouping the approval chain routes through, so the warning a
    colleague sees is the warning their approvers are routing against. Only
    *approved* plans' current/future reserved or confirmed blocks are visible
    to peers; drafts, submitted, rejected, cancelled and lapsed blocks never
    conflict. A block never conflicts with its own owner's plan.

    An owner with no team has no peers to conflict with, and a plan cannot be
    submitted without one in any case.
    """
    from users.models import EmployeeProfile, User

    profile = getattr(plan.employee, "employee_profile", None)
    if profile is None or profile.team_id is None:
        return []
    today = get_today()

    peer_ids = list(
        EmployeeProfile.objects.filter(
            user__is_active=True,
            team_id=profile.team_id,
        )
        .exclude(user_id=plan.employee_id)
        .values_list("user_id", flat=True)
    )
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
            # The name, not the row: this payload is returned to the browser.
            peer_department = ""
            if peer_profile is not None and peer_profile.department_id is not None:
                peer_department = peer_profile.department.name
            conflicts.append(
                {
                    "peer_name": other.plan.employee.get_full_name(),
                    "peer_department": peer_department,
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
    """Resolve the plan's approval chain, raising a list of ``FieldIssue``s.

    A cheap pre-flight over the provider's definitions, so the employee is told
    about an unstaffed section *before* the plan is parked anywhere. The
    provider has already removed the plan owner from every section they belong
    to, so an empty ``approver_user_ids`` means a section whose only member was
    the applicant — which cannot be routed at all.
    """
    definitions = _plan_stage_definitions(plan)

    missing = [
        f'No active approver for the "{definition.role_label}" approval section.'
        for definition in definitions
        if not definition.approver_user_ids
    ]
    if missing:
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message=message,
                )
                for message in missing
            ]
        )


def _plan_stage_definitions(plan: LeaveDayPlan):
    """The plan's validated chain of section definitions.

    Wraps the workflow provider — which resolves the employee's *team* and its
    workflow — and turns every configuration problem into a
    ``workflow_unavailable`` field issue, so the API has one code to map to 422
    regardless of whether the employee has no team, no active team, a workflow
    with no active sections, or mis-ordered sections.
    """
    from workflows.providers import WorkflowConfigError, get_workflow_provider

    try:
        definitions = get_workflow_provider().get_stage_definitions(plan)
    except WorkflowConfigError as exc:
        raise PlanValidationFailedError(
            [FieldIssue(field="—", code="workflow_unavailable", message=str(exc))]
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
    if sorted(d.order for d in definitions) != list(range(1, len(definitions) + 1)):
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message="Workflow stages must be ordered 1..N.",
                )
            ]
        )
    return definitions


def assign_plan_workflow(plan: LeaveDayPlan) -> PlanApprovalStage:
    """Materialise the plan's approval chain (plan-scoped ``assign_workflow``).

    Mirrors :func:`workflows.services.assign_workflow`, and shares its spine
    with it: the employee's team selects the workflow, every active section
    becomes one stage, and each stage snapshots **every** person the provider
    says may act on it (``StageDefinition.approver_user_ids``).

    **The chain always starts at section one, and no section is ever skipped.**
    The provider has already removed the plan owner from the sections they
    belong to, so there is no ``skipped`` status to produce and no
    ``select_activatable_stage_index`` to consult: a section the owner belongs
    to is still decided, by its other members, and a section whose only member
    was the owner cannot be routed at all, so the submission is refused there
    rather than left pending forever.

    Returns the first (pending) stage.
    """
    definitions = _plan_stage_definitions(plan)

    last_index = len(definitions) - 1
    stages = [
        PlanApprovalStage(
            plan=plan,
            submission_cycle=plan.submission_cycle,
            stage_order=definition.order,
            role=definition.role,
            role_label=definition.role_label or definition.role,
            role_ref_id=definition.role_id,
            history_scope=definition.history_scope or "",
            section_ref_id=definition.section_id,
            assigned_approver=None,
            status=_initial_stage_status(index),
            is_final=index == last_index,
        )
        for index, definition in enumerate(definitions)
    ]

    PlanApprovalStage.objects.bulk_create(stages)

    # Snapshot who may act on each section, now. This is what makes an in-flight
    # plan immune to later membership edits, and what self-approval is enforced
    # through: the owner is absent from these rows because the provider removed
    # them, so there is no self-approval check left to remember on any later read.
    PlanApprovalStageApprover.objects.bulk_create(
        PlanApprovalStageApprover(stage=stage, user_id=user_id)
        for stage, definition in zip(stages, definitions)
        for user_id in definition.approver_user_ids
    )

    first = stages[0]
    plan.current_stage = first
    # The next section is open, so nobody has taken it up yet and
    # ``current_approver`` is cleared: its members are read from the stage's
    # eligibility snapshot.
    plan.current_approver = None
    plan.save(update_fields=["current_stage", "current_approver", "updated_at"])
    return first


def _initial_stage_status(index: int) -> str:
    """The status a freshly materialised stage starts in.

    A chain always starts at its first section, so there is exactly one pending
    stage and the rest are waiting. A stage can no longer be born skipped: the
    owner is excluded from the eligibility snapshot instead of being jumped over.
    """
    if index == 0:
        return PlanApprovalStage.Status.PENDING
    return PlanApprovalStage.Status.WAITING


def submit_plan(*, user, plan_id):
    """Validate a draft plan and route it into the approval chain.

    Raises ``PlanNotFoundError`` (404), ``PlanNotSubmittableError`` (409) or
    ``PlanValidationFailedError`` (422). Returns the persisted plan on success.

    The whole submission is one transaction: the plan row is locked, and the
    status flip, the materialised approval chain and the audit entry land
    together. Without it a failure after the status write would strand a plan
    that reads ``submitted`` with nothing to approve, and ``select_for_update``
    would raise ``TransactionManagementError``.
    """
    with transaction.atomic():
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
                    "current_stage_order": active_stage.stage_order,
                    "current_stage_role": active_stage.role_label,
                    "current_stage_candidates": len(
                        active_stage.eligible_approver_ids()
                    ),
                },
            ),
        )

        from notifications.plans import notify_plan_assigned

        # The approvers must not be emailed until the chain they are being
        # pointed at is actually committed.
        transaction.on_commit(lambda p=plan.pk: notify_plan_assigned(p))

    return plan


def eligible_approver_ids(plan: LeaveDayPlan, stage=None) -> list[int]:
    """Every person entitled to act on the plan's pending stage, right now.

    The authorisation half of the spine, plan-scoped. A section is resolved by
    whoever acts first, so the authoritative answer is a *set* read from the
    stage's eligibility snapshot — never from ``current_approver``, which only
    records that somebody has already acted. The plan owner was removed from
    the snapshot when the chain was materialised, so self-approval cannot
    appear here.

    ``stage`` is an optional already-loaded :class:`PlanApprovalStage`, so a
    caller that prefetched ``eligible_approvers`` does not re-read the snapshot.
    """
    stage = stage if stage is not None else _current_stage(plan)
    if stage is None:
        return []
    return list(stage.eligible_approver_ids())


def _current_stage(plan: LeaveDayPlan):
    if plan.current_stage_id is None:
        return None
    return PlanApprovalStage.objects.filter(pk=plan.current_stage_id).first()


def acting_approver_ids(
    plan: LeaveDayPlan, eligible: list[int] | None = None
) -> list[int]:
    """The eligible people after delegation is applied.

    Anyone who can act, plus the delegate of any eligible person who has
    delegated while a delegation covers them. Single-level only: a delegate's own
    active delegation is never cascaded.
    """
    from workflows.services import _active_delegation_for_id

    if eligible is None:
        eligible = eligible_approver_ids(plan)
    if not eligible:
        return []
    result: list[int] = []
    for approver_id in eligible:
        delegation = _active_delegation_for_id(approver_id)
        if delegation is not None and delegation.delegate_id is not None:
            result.append(delegation.delegate_id)
        else:
            result.append(approver_id)
    return result


def user_may_act(user, plan: LeaveDayPlan, stage=None) -> bool:
    """Whether ``user`` is entitled to decide the plan's pending stage.

    The single authoritative authority check, plan-scoped. A person's authority
    comes from being in the stage's eligibility snapshot (or being an eligible
    approver's active delegate) — never from ``User.role``, and never from
    holding the same role in some other team's configuration.
    """
    user_id = user.id if hasattr(user, "id") else user
    if user_id is None:
        return False
    return user_id in acting_approver_ids(plan, eligible_approver_ids(plan, stage))


def responsible_approver_id(plan: LeaveDayPlan, stage=None) -> int | None:
    """The person who has taken up the pending stage, or the sole candidate.

    Display only. An unclaimed section can have several candidates, in which case
    there is no single "responsible" person and this returns ``None``; the
    payloads render that as the candidate list. Authorisation never reads this.
    """
    if plan.current_approver_id is not None:
        return plan.current_approver_id
    stage = stage if stage is not None else _current_stage(plan)
    if stage is None:
        return None
    if stage.assigned_approver_id is not None:
        return stage.assigned_approver_id
    eligible = stage.eligible_approver_ids()
    return eligible[0] if len(eligible) == 1 else None


def acting_approver_id(plan: LeaveDayPlan, stage=None) -> int | None:
    """The single user entitled to act now, or ``None`` when several may.

    Display only; see :func:`user_may_act` for the authority check. Returns
    ``None`` for an unclaimed section with more than one candidate, because
    naming one of them would be a guess.
    """
    acting = acting_approver_ids(plan, eligible_approver_ids(plan, stage))
    return acting[0] if len(acting) == 1 else None


def acting_approver_predicate(user) -> Q:
    """Query predicate selecting plans the user may act on now.

    Plan-scoped mirror of
    :func:`workflows.services.acting_approver_predicate`, with the same shape:
    explicit ``__in`` subqueries on ``current_stage_id`` rather than joins through
    the multi-valued ``eligible_approvers`` relation, and the same rule that a
    user away under an active delegation gets nothing of their own eligibility
    put in their queue while colleagues eligible for the same section keep theirs.
    """
    from django.utils import timezone

    from workflows.models import Delegation

    today = timezone.localdate()
    delegations = Delegation.objects.filter(
        status=Delegation.Status.APPROVED,
        starts_on__lte=today,
        delegate__isnull=False,
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    delegated_approver_ids = list(
        delegations.values_list("approver_id", flat=True).distinct()
    )
    received_approver_ids = list(
        delegations.filter(delegate=user)
        .values_list("approver_id", flat=True)
        .distinct()
    )
    own = Q(
        current_stage_id__in=PlanApprovalStageApprover.objects.filter(
            user=user
        ).values_list("stage_id", flat=True)
    )
    if user.pk in delegated_approver_ids:
        own = Q(pk__in=[])
    acting = (
        Q(
            current_stage_id__in=PlanApprovalStageApprover.objects.filter(
                user_id__in=received_approver_ids
            ).values_list("stage_id", flat=True)
        )
        if received_approver_ids
        else Q(pk__in=[])
    )
    return own | acting


def _lock_plan_and_stage(plan_id, actor):
    """Lock the plan row and its current stage.

    Must be called inside ``transaction.atomic()``.
    """
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
        # The plan owner is absent from the eligibility snapshot by construction,
        # so this check is belt-and-braces rather than the primary guard.
        if plan.employee_id == actor.pk or not user_may_act(actor, plan, stage):
            raise PlanDecisionNotAllowedError("not_current_stage")

        before_status = plan.status
        before_order = stage.stage_order
        before_version = stage.decision_version

        # Claim the stage by acting on it. A section is open to all of its
        # members, so this is the moment the stage stops being open: the
        # ``select_for_update`` in ``_lock_plan_and_stage`` is what makes the
        # claim exclusive, and the optimistic ``decision_version`` check refuses
        # the loser of a race with 409 rather than letting two people decide the
        # same section.
        stage.assigned_approver = actor
        plan.current_approver = actor

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
        # Persist the decided stage first so a single ``pending`` stage always
        # exists at any one moment (enforced by the partial unique constraint).
        stage.save(
            update_fields=[
                "status",
                "decision_version",
                "assigned_approver",
                "updated_at",
            ]
        )
        if next_stage is not None:
            next_stage.save(update_fields=["status", "decision_version", "updated_at"])
            plan.current_stage = next_stage
            # The spine follows the stage. The next section is open, so nobody has
            # taken it up yet and ``current_approver`` is cleared: its members
            # are read from the stage's eligibility snapshot.
            plan.current_approver = None

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

        from notifications.plans import notify_plan_assigned, notify_plan_decided

        next_stage_id = next_stage.id if next_stage is not None else None
        transaction.on_commit(lambda p=plan.pk, s=finalised: notify_plan_decided(p, s))
        if next_stage_id is not None:
            # The next section is now the live one, and it is open to all of its
            # members — so it is they who need telling, read from the new
            # stage's eligibility snapshot rather than from ``current_approver``.
            transaction.on_commit(lambda p=plan.pk: notify_plan_assigned(p))

    return plan


def _next_activatable_stage(plan, decided_stage):
    """The next stage to activate after ``decided_stage`` was approved.

    The chain is contiguous and nothing is ever bypassed, so this is simply the
    next stage by order. It is still looked up under a row lock and its
    eligibility re-checked, because a stage with nobody able to act is a chain
    that cannot finish and must be reported rather than activated as a dead end.

    Raises ``PlanDecisionValidationError`` when the chain simply ends (a
    pre-existing malformed chain) and ``PlanValidationFailedError`` when the next
    stage has no eligible approver — which means a section lost its membership
    after the chain was materialised, or holds only the plan owner.

    Must be called inside ``transaction.atomic()``.
    """
    remaining = list(
        PlanApprovalStage.objects.select_for_update()
        .filter(
            plan=plan,
            submission_cycle=plan.submission_cycle,
            stage_order__gt=decided_stage.stage_order,
        )
        .order_by("stage_order")
    )
    if not remaining:
        raise PlanDecisionValidationError(
            {"action": "Workflow chain is incomplete."}
        )

    candidate = remaining[0]
    if not candidate.eligible_approvers.exists():
        raise PlanValidationFailedError(
            [
                FieldIssue(
                    field="—",
                    code="workflow_unavailable",
                    message=(
                        "This plan cannot be advanced: nobody can act on the "
                        f"{candidate.role_label} stage, so there is no approver "
                        "left to sign it off. An approver cannot approve their "
                        "own leave day plan, and a mandatory section cannot be "
                        "skipped. Human Resources must appoint another member of "
                        "that section, or change the workflow, before this plan "
                        "can be decided."
                    ),
                )
            ]
        )
    return candidate


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