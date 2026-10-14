"""Pure payload builders for the Unit 18 cancellation API.

The employee endpoints (cancellation-eligibility/, cancel/, cancellations/) and
the approver cancellation endpoints (approvals/cancellations/) all speak these
shapes. They are read-only view helpers; every value derives from persisted
state or the eligibility service, never from a mutable buffer.
"""

from __future__ import annotations

from decimal import Decimal

from .models import CancellationApprovalStage, CancellationRequest


def _user_name(pk) -> str | None:
    if pk is None:
        return None
    from users.models import User

    user = User.objects.filter(pk=pk).first()
    if user is None:
        return None
    return user.get_full_name() or user.username


def eligibility_payload(application, eligibility, today=None):
    """The GET cancellation-eligibility payload (spec 3.4)."""
    from .providers import get_today as _today

    tod = today if today is not None else _today()
    started = application.start_date is not None and application.start_date <= tod
    starts_in_days = None
    if not started and application.start_date is not None:
        starts_in_days = (application.start_date - tod).days

    return {
        "application_id": str(application.id),
        "reference": application.reference_number,
        "cancellation_action": eligibility.cancellation_action,
        "cancellation_blocked_reason": eligibility.cancellation_blocked_reason,
        "estimated_restoration_days": (
            _days(eligibility.estimated_restoration_days)
            if eligibility.estimated_restoration_days is not None
            else None
        ),
        "restoration_financial_year": eligibility.restoration_financial_year,
        "leave_started": started,
        "starts_in_days": starts_in_days,
    }


def request_summary(request: CancellationRequest) -> dict:
    """One cancellation request with its stages (employee history + approver)."""
    return {
        "id": str(request.id),
        "kind": request.kind,
        "status": request.status,
        "reason": request.reason,
        "requested_at": _iso(request.requested_at),
        "decided_at": _iso(request.decided_at),
        "stage_version": request.stage_version,
        "application_status_at_request": request.application_status_at_request,
        "balance_restored_days": _days(request.balance_restored_days),
        "restored_financial_year": request.restored_financial_year,
        "employee_notification_state": request.employee_notification_state,
        "stages": [
            _stage_payload(stage) for stage in request.stages.all()
        ],
    }


def approver_row(request: CancellationRequest, today=None) -> dict:
    """One row of the approver cancellation queue (spec 3.8)."""
    from .providers import get_today as _today

    application = request.application
    tod = today if today is not None else _today()
    started = application.start_date is not None and application.start_date <= tod
    starts_in_days = None
    if not started and application.start_date is not None:
        starts_in_days = (application.start_date - tod).days

    current = (
        CancellationApprovalStage.objects.filter(
            request=request,
            status=CancellationApprovalStage.Status.PENDING,
        )
        .only("role", "role_label")
        .first()
    )
    return {
        "request_id": str(request.id),
        "application_id": str(application.id),
        "reference": application.reference_number,
        "employee_name": application.employee.get_full_name()
        or application.employee.username,
        "leave_type": _leave_type_block(application),
        "start_date": _iso_date(application.start_date),
        "end_date": _iso_date(application.end_date),
        "working_days": application.working_days,
        "requested_at": _iso(request.requested_at),
        "current_stage_role": current.role if current else None,
        "current_stage_role_label": current.role_label if current else None,
        "stage_version": request.stage_version,
        "leave_started": started,
        "starts_in_days": starts_in_days,
    }


def approver_detail(request: CancellationRequest, user, today=None) -> dict:
    """The full cancellation detail payload (spec 3.9)."""
    from .providers import get_today as _today

    application = request.application
    tod = today if today is not None else _today()
    stages = list(request.stages.all().select_related("approver"))

    pending = next(
        (s for s in stages if s.status == CancellationApprovalStage.Status.PENDING),
        None,
    )
    # A section is decided by any of its snapshotted members, so authority is
    # membership in the open stage's set rather than equality with one person.
    can_decide = (
        pending is not None
        and request.status == CancellationRequest.Status.PENDING
        and user.id in pending.eligible_approver_ids()
    )
    my_stage = next(
        (s for s in stages if s.approver_id == user.id), None
    )
    my_decision = None
    if my_stage is not None and my_stage.decided_at is not None:
        my_decision = {
            "decision": (
                CancellationApprovalStage.Status.APPROVED
                if my_stage.status == CancellationApprovalStage.Status.APPROVED
                else CancellationApprovalStage.Status.REJECTED
            ),
            "decided_at": _iso(my_stage.decided_at),
            "comment": my_stage.comment,
        }

    return {
        "request": request_summary(request),
        "requested_by_name": (
            request.requested_by.get_full_name() or request.requested_by.username
        ),
        "stage_version": request.stage_version,
        "my_decision": my_decision,
        "can_decide": can_decide,
        "application": {
            "id": str(application.id),
            "reference": application.reference_number,
            "status": application.status,
            "leave_type": _leave_type_block(application),
            "start_date": _iso_date(application.start_date),
            "end_date": _iso_date(application.end_date),
            "working_days": application.working_days,
            "calendar_days": application.calendar_days,
            "reason": application.reason,
            "financial_year_label": application.financial_year_label,
            "submitted_at": _iso(application.submitted_at),
        },
        "balance_impact": {
            "restore_days": _days(request.balance_restored_days),
            "restore_financial_year": request.restored_financial_year,
        },
        "leave_started": (
            application.start_date is not None and application.start_date <= tod
        ),
    }


def _stage_payload(stage: CancellationApprovalStage) -> dict:
    """One cancellation stage for the stepper.

    ``approver_name`` is null while the stage is open: a section is resolved by
    whoever acts first, so nobody owns it until a decision lands.
    ``eligible_approvers`` carries the snapshot instead.
    """
    eligible_names = [
        name
        for name in (_user_name(uid) for uid in stage.eligible_approver_ids())
        if name
    ]
    return {
        "id": str(stage.id),
        "order": stage.order,
        "role": stage.role,
        "role_label": stage.role_label,
        "status": stage.status,
        "approver_name": (
            stage.approver.get_full_name() or stage.approver.username
            if stage.approver_id
            else None
        ),
        "eligible_approvers": eligible_names,
        "decided_at": _iso(stage.decided_at),
        "comment": stage.comment or None,
    }


def _leave_type_block(application) -> dict:
    snapshot = (application.rules_snapshot or {}).get("leave_type")
    if snapshot:
        return {
            "id": snapshot.get("id"),
            "code": snapshot.get("code"),
            "name": snapshot.get("name"),
        }
    return {
        "id": application.leave_type_id,
        "code": None,
        "name": f"Leave type #{application.leave_type_id}",
    }


def _days(value) -> str:
    return f"{Decimal(value):.1f}" if value is not None else "0.0"


def _iso_date(value):
    return value.isoformat() if value else None


def _iso(value):
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")