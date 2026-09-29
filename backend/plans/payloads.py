"""Plan read payload builders (Unit 25).

Pure functions translating ``LeaveDayPlan`` + block/stage/decision rows into
the API shapes the dashboard needs. Every value is derived from persisted
state; the only live computation is the owner-facing peer-conflict warning.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal


from leave.models import LeaveType
from leave.providers import get_today

from .models import (
    LeaveDayPlan,
    LeavePlanBlock,
    PlanApprovalDecision,
    PlanApprovalStage,
)

_PUBLISHED_BLOCK_STATUSES = (
    LeavePlanBlock.Status.RESERVED,
    LeavePlanBlock.Status.CONFIRMED,
)


def _iso_date(value) -> str | None:
    return value.isoformat() if value else None


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _take(name):
    from workflows.models import STAGE_ROLE_LABELS

    return STAGE_ROLE_LABELS.get(name, name)


def block_payload(block: LeavePlanBlock, *, for_owner: bool) -> dict:
    from .services import _confirmation_window_start

    today = get_today()
    leave_type = (
        LeaveType.objects.filter(pk=block.leave_type_id).only("id", "code", "name").first()
        if block.leave_type_id
        else None
    )
    can_release = for_owner and block.start_date > today and block.status in (
        LeavePlanBlock.Status.RESERVED,
        LeavePlanBlock.Status.CONFIRMED,
    )
    can_confirm = for_owner and block.status == LeavePlanBlock.Status.RESERVED and block.start_date > today
    return {
        "id": str(block.id),
        "leave_type_id": block.leave_type_id,
        "leave_type_code": leave_type.code if leave_type else None,
        "leave_type_name": leave_type.name if leave_type else None,
        "start_date": _iso_date(block.start_date),
        "end_date": _iso_date(block.end_date),
        "working_days": block.working_days,
        "status": block.status,
        "status_label": LeavePlanBlock.Status(block.status).label
        if block.status
        else block.status,
        "confirmation_window_start": (
            _iso_date(_confirmation_window_start(block))
            if for_owner and block.status == LeavePlanBlock.Status.RESERVED
            else None
        ),
        "confirmed_at": _iso(block.confirmed_at),
        "released_at": _iso(block.released_at),
        "application_id": str(block.application_id) if block.application_id else None,
        "can_confirm": can_confirm,
        "can_release": can_release,
    }


def stage_payload(stage: PlanApprovalStage) -> dict:
    return {
        "id": str(stage.id),
        "stage_order": stage.stage_order,
        "role": stage.role,
        "role_label": stage.role_label or _take(stage.role),
        "assigned_approver_id": stage.assigned_approver_id,
        "approver_name": (
            stage.assigned_approver.get_full_name()
            if stage.assigned_approver_id
            else ""
        ),
        "status": stage.status,
        "status_label": PlanApprovalStage.Status(stage.status).label
        if stage.status
        else stage.status,
        "is_final": stage.is_final,
        "decision_version": stage.decision_version,
    }


def decision_payload(decision: PlanApprovalDecision) -> dict:
    return {
        "id": str(decision.id),
        "stage_order": decision.stage.stage_order,
        "role_label": decision.role_label,
        "approver_name": decision.approver_name,
        "action": decision.action,
        "comment": decision.comment,
        "decided_at": _iso(decision.decided_at),
    }


def _plan_meta(plan: LeaveDayPlan) -> dict:
    return {
        "id": str(plan.id),
        "period_start": _iso_date(plan.period_start),
        "period_end": _iso_date(plan.period_end),
        "financial_year_label": plan.financial_year_label or "",
        "status": plan.status,
        "status_label": LeaveDayPlan.Status(plan.status).label
        if plan.status
        else plan.status,
        "submitted_at": _iso(plan.submitted_at),
        "decided_at": _iso(plan.decided_at),
        "submission_cycle": plan.submission_cycle,
    }


def plan_row(plan: LeaveDayPlan, user, *, scope: str) -> dict:
    """One row for mine/team/department/admin lists under ``scope``."""
    row = _plan_meta(plan)
    row["employee_id"] = plan.employee_id
    row["employee_name"] = plan.employee.get_full_name() or plan.employee.username
    blocks = _visible_blocks(plan, user, scope)
    row["block_count"] = len(blocks)
    row["working_days"] = sum(
        (b.working_days or 0) for b in blocks if b.working_days is not None
    )
    row["blocks"] = [block_payload(b, for_owner=plan.employee_id == user.pk) for b in blocks]
    if plan.employee_id == user.pk:
        from .services import peer_conflicts

        row["peer_conflicts"] = peer_conflicts(plan)
    return row


def _visible_blocks(plan: LeaveDayPlan, user, scope: str):
    today = get_today()
    qs = plan.plan_blocks.order_by("start_date", "end_date")
    if scope in ("owner", "approver", "hr", "all") or plan.employee_id == user.pk:
        return list(qs)
    if plan.status != LeaveDayPlan.Status.APPROVED:
        return []
    return [b for b in qs if b.status in _PUBLISHED_BLOCK_STATUSES and b.end_date >= today]


def plan_detail_payload(plan: LeaveDayPlan, user, access) -> dict:
    from .policies import plan_view_access

    access = access or plan_view_access(user, plan)
    is_owner = plan.employee_id == user.pk
    payload = {
        "meta": _plan_meta(plan),
        "employee": {
            "id": plan.employee_id,
            "name": plan.employee.get_full_name() or plan.employee.username,
        },
        "blocks": [
            block_payload(b, for_owner=is_owner)
            for b in plan.plan_blocks.order_by("start_date", "end_date")
        ],
        "stages": [
            stage_payload(s)
            for s in plan.approval_stages.order_by("stage_order").select_related(
                "assigned_approver"
            )
        ],
        "decisions": [
            decision_payload(d)
            for d in plan.approval_decisions.order_by("decided_at").select_related("stage")
        ],
        "access": access.scope if access else None,
        "can_decide": bool(access and access.can_decide),
        "can_submit": bool(is_owner and plan.status == LeaveDayPlan.Status.DRAFT),
        "my_decision": _my_decision(plan, user),
    }
    if is_owner:
        from .services import peer_conflicts

        payload["peer_conflicts"] = peer_conflicts(plan)
        payload["pending_confirmations"] = [
            block_payload(b, for_owner=True)
            for b in plan.plan_blocks.filter(
                status=LeavePlanBlock.Status.RESERVED,
                end_date__gte=get_today(),
                start_date__gt=get_today(),
            )[:50]
        ]
    return payload


def _my_decision(plan: LeaveDayPlan, user):
    decision = (
        plan.approval_decisions.filter(approver=user, submission_cycle=plan.submission_cycle)
        .select_related("stage")
        .order_by("-decided_at")
        .first()
    )
    if decision is None:
        return None
    return {
        "action": decision.action,
        "stage_order": decision.stage.stage_order,
        "decided_at": _iso(decision.decided_at),
    }


def approver_list_row(plan: LeaveDayPlan, user) -> dict:
    decision = (
        plan.approval_decisions.filter(approver=user, submission_cycle=plan.submission_cycle)
        .order_by("-decided_at")
        .first()
    )
    stage = plan.current_stage
    return {
        **_plan_meta(plan),
        "employee_name": plan.employee.get_full_name() or plan.employee.username,
        "department": _department(plan),
        "submitted_at": _iso(plan.submitted_at),
        "stage_role_label": (stage.role_label if stage else ""),
        "my_decision": (
            {"action": decision.action, "decided_at": _iso(decision.decided_at)}
            if decision
            else None
        ),
        "blocks": [
            {
                "leave_type_code": LeaveType.objects.filter(
                    pk=b.leave_type_id
                ).values_list("code", flat=True).first(),
                "start_date": _iso_date(b.start_date),
                "end_date": _iso_date(b.end_date),
                "working_days": b.working_days,
            }
            for b in plan.plan_blocks.order_by("start_date", "end_date")
        ],
    }


def approver_detail_payload(plan: LeaveDayPlan, user) -> dict:
    from .services import acting_approver_id

    stage = plan.current_stage
    is_current = (
        stage is not None
        and stage.status == PlanApprovalStage.Status.PENDING
        and acting_approver_id(plan) == user.pk
    )
    return {
        "meta": _plan_meta(plan),
        "employee": {
            "id": plan.employee_id,
            "name": plan.employee.get_full_name() or plan.employee.username,
            "department": _department(plan),
        },
        "blocks": [
            block_payload(b, for_owner=False)
            for b in plan.plan_blocks.order_by("start_date", "end_date")
        ],
        "stages": [
            stage_payload(s)
            for s in plan.approval_stages.order_by("stage_order").select_related(
                "assigned_approver"
            )
        ],
        "decisions": [
            decision_payload(d)
            for d in plan.approval_decisions.order_by("decided_at").select_related("stage")
        ],
        "can_decide": is_current and plan.employee_id != user.pk,
        "decision_version": stage.decision_version if stage else None,
        "my_decision": _my_decision(plan, user),
    }


def _department(plan: LeaveDayPlan) -> str:
    try:
        profile = plan.employee.employee_profile
    except Exception:
        return ""
    return (profile.department or "") if profile else ""