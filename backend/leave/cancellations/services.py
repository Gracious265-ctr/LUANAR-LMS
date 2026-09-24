"""Cancellation service layer (Unit 18, spec 3.4/3.5).

Every command runs inside ``transaction.atomic()`` and takes locks in the
specified order (application row first, then request, then stages) so an
approver decision racing an employee withdrawal serialises on the application
row: exactly one wins and the other gets a 409.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from django.db import transaction
from django.utils import timezone

from workflows.models import STAGE_ROLE_LABELS, ApplicationStage

from ..models import LeaveApplication
from .events import (
    CANCELLATION_APPROVED,
    CANCELLATION_REJECTED,
    CANCELLATION_REQUESTED,
    CANCELLATION_STAGE_APPROVED,
    CANCELLATION_WITHDRAWN,
    CancellationEvent,
    emit_cancellation_event,
)
from .models import CancellationApprovalStage, CancellationRequest
from .providers import get_balance_provider, get_today

#: Decision verbs for :func:`decide_cancellation` (spec 3.5).
DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"


class CancellationError(Exception):
    """Base class for cancellation command failures."""


class ApplicationNotFoundError(CancellationError):
    """The application does not exist or belongs to another employee (404)."""


class NotCancellableError(CancellationError):
    """The application cannot be cancelled; carries the blocked-reason code."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ActionChangedError(CancellationError):
    """Eligibility changed since the client loaded it; carries fresh state (409)."""

    def __init__(self, eligibility):
        self.eligibility = eligibility
        super().__init__("action_changed")


class LeaveAlreadyStartedError(CancellationError):
    """The leave has started, so approval is refused (409)."""


class OpenRequestExistsError(CancellationError):
    """The application already has an open cancellation request (409)."""


class NoCancellationApproversError(CancellationError):
    """The workflow snapshot has no Supervisor/HOD stage (422)."""


class ConfirmationRequiredError(CancellationError):
    """The client must send ``confirm: true`` (400)."""


class ReasonTooShortError(CancellationError):
    """The reason is under 10 characters after trimming (400)."""


class ReasonTooLongError(CancellationError):
    """The reason is over 1000 characters after trimming (400)."""


class RequestNotFoundError(CancellationError):
    """The cancellation request does not exist (404)."""


class RequestNotPendingError(CancellationError):
    """The request is no longer pending (409 ``request_not_pending``)."""


class StaleStageVersionError(CancellationError):
    """The decision's ``stage_version`` is stale (409 ``stale_stage_version``)."""


class NotCurrentApproverError(CancellationError):
    """The user is not the approver of the current pending stage (403)."""


class CommentRequiredError(CancellationError):
    """A comment is required for a rejection (400)."""


class CommentTooLongError(CancellationError):
    """The comment is over the 1000 character limit (400)."""


@dataclass(frozen=True)
class Eligibility:
    """The cancellation eligibility for one application (spec 3.4)."""

    cancellation_action: Optional[str]  # "withdraw" | "request" | None
    cancellation_blocked_reason: Optional[str]
    estimated_restoration_days: Optional[Decimal]
    restoration_financial_year: Optional[str]


def get_eligibility(
    application,
    user,
    *,
    today=None,
    open_request: CancellationRequest | None = None,
) -> Eligibility:
    """Compute what the owning employee can do with ``application``.

    ``today`` is injectable for tests and defaults to LUANAR local time.
    ``open_request`` short-circuits the open-request query when the caller has
    already loaded the latest request (the tracking service does).
    """
    status = application.status
    if status not in (LeaveApplication.Status.SUBMITTED, LeaveApplication.Status.APPROVED):
        return Eligibility(None, "not_cancellable_status", None, None)

    open_request = open_request
    if open_request is None and status == LeaveApplication.Status.APPROVED:
        open_request = (
            CancellationRequest.objects.filter(
                application=application,
                status=CancellationRequest.Status.PENDING,
            )
            .order_by("-requested_at")
            .first()
        )

    if status == LeaveApplication.Status.SUBMITTED:
        return Eligibility("withdraw", None, None, None)

    if open_request is not None:
        return Eligibility(None, "open_request_exists", None, None)

    tod = today if today is not None else get_today()
    if application.start_date is None or application.start_date <= tod:
        return Eligibility(None, "leave_already_started", None, None)

    from workflows.providers import get_workflow_provider

    stages = get_workflow_provider().get_cancellation_stages(application)
    if not stages or any(stage.approver_user_id is None for stage in stages):
        return Eligibility(None, "no_cancellation_approvers", None, None)

    deduction = get_balance_provider().get_deduction(application)
    if deduction is None:
        return Eligibility(
            "request",
            None,
            Decimal(0),
            None,
        )
    return Eligibility(
        "request",
        None,
        deduction.days,
        deduction.financial_year,
    )


def submit_cancellation(
    *,
    user,
    application_id,
    reason,
    confirm: bool,
    expected_action: str | None,
    today=None,
) -> CancellationRequest:
    """Cancel the owned application: withdraw if pending, request if approved.

    Raises ``ApplicationNotFoundError`` (404), ``ActionChangedError`` /
    ``NotCancellableError`` / ``LeaveAlreadyStartedError`` /
    ``OpenRequestExistsError`` (409), ``NoCancellationApproversError`` (422) or
    the 400 validation errors. Returns the persisted :class:`CancellationRequest`.
    """
    with transaction.atomic():
        application = (
            LeaveApplication.objects.select_for_update()
            .filter(id=application_id, employee=user)
            .first()
        )
        if application is None:
            raise ApplicationNotFoundError()

        eligibility = get_eligibility(
            application, user, today=today
        )
        action = eligibility.cancellation_action
        if expected_action != action:
            raise ActionChangedError(eligibility)

        if not confirm:
            raise ConfirmationRequiredError()

        reason = (reason or "").strip()
        if len(reason) < 10:
            raise ReasonTooShortError()
        if len(reason) > 1000:
            raise ReasonTooLongError()

        if action is None:
            reason = eligibility.cancellation_blocked_reason or "not_cancellable_status"
            if reason == "no_cancellation_approvers":
                raise NoCancellationApproversError()
            raise NotCancellableError(reason)

        now = timezone.now()
        if action == "withdraw":
            return _withdraw(application, user, reason, now)
        return _request(application, user, reason, now)


def _withdraw(application, user, reason: str, now) -> CancellationRequest:
    """Withdraw a pending application immediately (spec 3.5 step 4)."""
    previous_status = application.status
    previous_stage_order = (
        application.current_stage.stage_order
        if application.current_stage_id is not None
        else None
    )

    request = CancellationRequest.objects.create(
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.WITHDRAWAL,
        reason=reason,
        status=CancellationRequest.Status.APPROVED,
        stage_version=1,
        requested_at=now,
        decided_at=now,
        application_status_at_request=previous_status,
        employee_notification_state=CancellationRequest.NotificationState.NOT_REQUIRED,
    )

    ApplicationStage.objects.filter(
        application=application,
        submission_cycle=application.workflow_chain_cycle,
        status=ApplicationStage.Status.PENDING,
    ).update(status=ApplicationStage.Status.CANCELLED)

    application.status = LeaveApplication.Status.CANCELLED
    application.cancelled_at = now
    application.current_stage = None
    application.current_approver = None
    application.save(
        update_fields=[
            "status",
            "cancelled_at",
            "current_stage",
            "current_approver",
            "updated_at",
        ]
    )

    record_audit(
        actor=user,
        action=AuditEntry.Action.CANCELLATION_WITHDRAWN,
        target_type=AuditEntry.TargetType.CANCELLATION,
        target_id=request.pk,
        target_summary=application.reference_number,
        detail=changed_fields(
            {
                "status": previous_status,
                "current_stage_order": previous_stage_order,
            },
            {
                "status": LeaveApplication.Status.CANCELLED,
                "current_stage_order": None,
            },
        ),
        reason=reason,
    )

    recipients = _event_recipients(application)
    event = CancellationEvent(
        kind=CANCELLATION_WITHDRAWN,
        application_id=str(application.pk),
        request_id=str(request.pk),
        outcome=CancellationRequest.Status.APPROVED,
        recipient_user_ids=recipients,
    )
    transaction.on_commit(lambda e=event: emit_cancellation_event(e))
    return request


def _request(application, user, reason: str, now) -> CancellationRequest:
    """Create an approval-based cancellation request (spec 3.5 step 5)."""
    from workflows.providers import get_workflow_provider

    stages_spec = get_workflow_provider().get_cancellation_stages(application)
    if not stages_spec or any(
        stage.approver_user_id is None for stage in stages_spec
    ):
        raise NoCancellationApproversError()

    if CancellationRequest.objects.filter(
        application=application,
        status=CancellationRequest.Status.PENDING,
    ).exists():
        raise OpenRequestExistsError()

    request = CancellationRequest.objects.create(
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.APPROVED_LEAVE,
        reason=reason,
        status=CancellationRequest.Status.PENDING,
        stage_version=1,
        requested_at=now,
        application_status_at_request=application.status,
        employee_notification_state=CancellationRequest.NotificationState.NOT_REQUIRED,
    )

    first = True
    for spec in stages_spec:
        CancellationApprovalStage.objects.create(
            request=request,
            order=spec.order,
            role=spec.role,
            role_label=STAGE_ROLE_LABELS.get(spec.role, spec.role),
            approver_id=spec.approver_user_id,
            status=(
                CancellationApprovalStage.Status.PENDING
                if first
                else CancellationApprovalStage.Status.WAITING
            ),
        )
        first = False

    record_audit(
        actor=user,
        action=AuditEntry.Action.CANCELLATION_REQUESTED,
        target_type=AuditEntry.TargetType.CANCELLATION,
        target_id=request.pk,
        target_summary=application.reference_number,
        detail=changed_fields(
            {
                "status": application.status,
                "kind": None,
            },
            {
                "status": application.status,
                "kind": CancellationRequest.Kind.APPROVED_LEAVE,
            },
        ),
        reason=reason,
    )

    event = CancellationEvent(
        kind=CANCELLATION_REQUESTED,
        application_id=str(application.pk),
        request_id=str(request.pk),
        outcome=CancellationRequest.Status.PENDING,
        recipient_user_ids=_event_recipients(application),
    )
    transaction.on_commit(lambda e=event: emit_cancellation_event(e))
    return request


def decide_cancellation(
    *,
    user,
    request_id,
    decision: str,
    comment: str = "",
    stage_version: int,
    today=None,
) -> CancellationRequest:
    """Decide the current stage of an open cancellation request (spec 3.5).

    ``decision`` is ``approve`` or ``reject``. Raises ``RequestNotFoundError``
    (404), ``RequestNotPendingError`` / ``StaleStageVersionError`` /
    ``LeaveAlreadyStartedError`` (409), ``NotCurrentApproverError`` (403), or the
    400 comment errors. On final approval the annual deduction (if any) is
    restored idempotently to the originally debited financial year.
    """
    with transaction.atomic():
        request = (
            CancellationRequest.objects.filter(id=request_id)
            .select_related("application")
            .first()
        )
        if request is None:
            raise RequestNotFoundError()

        application = LeaveApplication.objects.select_for_update().get(
            pk=request.application_id
        )
        request = CancellationRequest.objects.select_for_update().get(pk=request_id)

        if request.status != CancellationRequest.Status.PENDING:
            raise RequestNotPendingError()
        if request.stage_version != stage_version:
            raise StaleStageVersionError()

        stage = (
            CancellationApprovalStage.objects.select_for_update()
            .filter(
                request=request,
                status=CancellationApprovalStage.Status.PENDING,
            )
            .first()
        )
        if stage is None:
            raise RequestNotPendingError()
        if stage.approver_id != user.id:
            raise NotCurrentApproverError()

        comment = (comment or "").strip()
        if len(comment) > 1000:
            raise CommentTooLongError()
        if decision == DECISION_REJECT:
            if not comment:
                raise CommentRequiredError()
        elif decision != DECISION_APPROVE:
            raise CommentRequiredError()  # pragma: no cover - serializer guards

        now = timezone.now()
        return _apply_decision(
            request=request,
            application=application,
            stage=stage,
            user=user,
            decision=decision,
            comment=comment,
            now=now,
            today=today,
        )


def _apply_decision(
    *, request, application, stage, user, decision, comment, now, today
) -> CancellationRequest:
    before_request = _request_state(request)
    before_stage = _stage_state(stage)

    if decision == DECISION_REJECT:
        stage.status = CancellationApprovalStage.Status.REJECTED
        stage.decided_at = now
        stage.comment = comment
        CancellationApprovalStage.objects.filter(
            request=request,
            order__gt=stage.order,
            status=CancellationApprovalStage.Status.WAITING,
        ).update(status=CancellationApprovalStage.Status.NOT_REACHED)
        request.status = CancellationRequest.Status.REJECTED
        request.decided_at = now
        request.employee_notification_state = (
            CancellationRequest.NotificationState.PENDING
        )
        outcome = CancellationRequest.Status.REJECTED
        event_kind = CANCELLATION_REJECTED
        audit_action = AuditEntry.Action.CANCELLATION_REJECTED
    else:
        next_stage = (
            CancellationApprovalStage.objects.select_for_update()
            .filter(
                request=request,
                order__gt=stage.order,
                status=CancellationApprovalStage.Status.WAITING,
            )
            .order_by("order")
            .first()
        )
        is_final = next_stage is None
        tod = today if today is not None else get_today()
        if is_final:
            if application.start_date is None or application.start_date <= tod:
                # The request stays untouched so the approver can still reject.
                raise LeaveAlreadyStartedError()
            stage.status = CancellationApprovalStage.Status.APPROVED
            stage.decided_at = now
            stage.comment = comment or ""
            request.status = CancellationRequest.Status.APPROVED
            request.decided_at = now
            request.employee_notification_state = (
                CancellationRequest.NotificationState.PENDING
            )

            application.status = LeaveApplication.Status.CANCELLED
            application.cancelled_at = now
            application.save(
                update_fields=["status", "cancelled_at", "updated_at"]
            )

            _restore_balance(application=application, request=request)

            outcome = CancellationRequest.Status.APPROVED
            event_kind = CANCELLATION_APPROVED
            audit_action = AuditEntry.Action.CANCELLATION_APPROVED
        else:
            stage.status = CancellationApprovalStage.Status.APPROVED
            stage.decided_at = now
            stage.comment = comment or ""
            # Persist the decided stage first so the partial unique constraint
            # (exactly one ``pending`` stage per request) holds at every instant.
            stage.save(
                update_fields=["status", "decided_at", "comment", "updated_at"]
            )
            next_stage.status = CancellationApprovalStage.Status.PENDING
            next_stage.save(update_fields=["status", "updated_at"])
            outcome = "stage_approved"
            event_kind = CANCELLATION_STAGE_APPROVED
            audit_action = AuditEntry.Action.CANCELLATION_STAGE_APPROVED

    request.stage_version += 1
    request.save(
        update_fields=[
            "status",
            "stage_version",
            "decided_at",
            "employee_notification_state",
            "balance_restored_days",
            "restored_financial_year",
            "updated_at",
        ]
    )
    stage.save(
        update_fields=["status", "decided_at", "comment", "updated_at"]
    )

    record_audit(
        actor=user,
        action=audit_action,
        target_type=AuditEntry.TargetType.CANCELLATION,
        target_id=request.pk,
        target_summary=application.reference_number,
        detail=changed_fields(
            {"request": before_request, "stage": before_stage},
            {
                "request": _request_state(request),
                "stage": _stage_state(stage),
            },
        ),
        reason=comment,
    )

    event = CancellationEvent(
        kind=event_kind,
        application_id=str(application.pk),
        request_id=str(request.pk),
        outcome=outcome,
        recipient_user_ids=_event_recipients(application),
    )
    transaction.on_commit(lambda e=event: emit_cancellation_event(e))
    return request


def _restore_balance(*, application, request) -> None:
    """Record the idempotent restoration for the finally approved cancellation."""
    provider = get_balance_provider()
    deduction = provider.get_deduction(application)
    if deduction is None:
        return

    provider.record_restoration(
        application,
        request,
        deduction.days,
        deduction.financial_year,
    )
    request.balance_restored_days = deduction.days
    request.restored_financial_year = deduction.financial_year

    record_audit(
        actor=request.requested_by,
        action=AuditEntry.Action.BALANCE_RESTORED,
        target_type=AuditEntry.TargetType.BALANCE_TRANSACTION,
        target_id=request.pk,
        target_summary=f"{application.reference_number} → FY {deduction.financial_year}",
        detail={
            "before": {"days": "0", "financial_year": None},
            "after": {
                "days": str(deduction.days),
                "financial_year": deduction.financial_year,
                "carry_forward_eligible": False,
            },
        },
    )


def _event_recipients(application) -> list[int]:
    """The employee plus every workflow member in the original snapshot."""
    from workflows.providers import get_workflow_provider

    member_ids = set(
        get_workflow_provider().get_workflow_member_user_ids(application)
    )
    member_ids.add(application.employee_id)
    return sorted(member_ids)


def _request_state(request) -> dict:
    return {
        "status": request.status,
        "stage_version": request.stage_version,
        "notification_state": request.employee_notification_state,
        "balance_restored_days": str(request.balance_restored_days),
    }


def _stage_state(stage) -> dict:
    return {
        "status": stage.status,
        "order": stage.order,
        "comment": stage.comment,
    }