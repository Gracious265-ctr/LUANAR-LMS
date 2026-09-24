"""Cancellation services (Unit 18, section 3.5).

Implements ``submit_cancellation``, ``decide_cancellation``, and
``get_eligibility``. All commands run inside ``transaction.atomic()`` and lock
in the guaranteed order — **application row first, then request, then stages**
(``select_for_update``) — to avoid deadlocks. "Today" always goes through
``leave.providers.get_today`` (the single injectable clock seam, section 3.4).

Audit rows are written in the same transaction as the state change, and domain
events fire on ``on_commit`` (sections 3.6/3.7).
"""

from decimal import Decimal

from audit.services import record_event
from django.db import transaction
from django.utils import timezone

from workflows.models import ApplicationStage

from ..models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveApplication,
)
from ..providers import get_today
from .balance import BalanceProvider, DeductionInfo
from .events import emit


class ApplicationNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class NotCancellableError(Exception):
    """The application status does not allow cancellation."""


class LeaveAlreadyStartedError(Exception):
    """The leave has already started; cancellation is blocked."""


class OpenRequestExistsError(Exception):
    """An open cancellation request already exists."""


class NoCancellationApproversError(Exception):
    """No Supervisor/HOD stages exist in the application's snapshot."""


class ActionChangedError(Exception):
    """The computed eligibility action differs from the client's expected one."""


class RequestNotPendingError(Exception):
    """The cancellation request is not pending."""


class StaleStageVersionError(Exception):
    """The client's stage version is stale."""


class NotCurrentApproverError(Exception):
    """The user is not the assigned approver on the current stage."""


class ConfirmationRequiredError(Exception):
    """The ``confirm`` flag is missing."""


class CommentRequiredError(Exception):
    """A comment is required for a rejection (or a comment is invalid)."""


class ReasonTooShortError(Exception):
    """The reason is under 10 characters."""


class ReasonTooLongError(Exception):
    """The reason is over 1000 characters."""


CANCELLABLE_STATUSES = (
    LeaveApplication.Status.PENDING,
    LeaveApplication.Status.APPROVED,
)

MIN_REASON_LENGTH = 10
MAX_REASON_LENGTH = 1000


def _blocked(reason: str) -> dict:
    return {
        "cancellation_action": None,
        "cancellation_blocked_reason": reason,
        "estimated_restoration_days": Decimal("0"),
        "restoration_financial_year": None,
    }


def compute_cancellation_eligibility(application) -> dict:
    """Compute the section-3.4 eligibility block for ``application``.

    Does **not** check ownership (the employee command and the Unit 15 tracking
    overlay both call it after their own ownership/visibility checks). Returns
    ``cancellation_action`` (``withdraw`` | ``request`` | ``None``),
    ``cancellation_blocked_reason``, ``estimated_restoration_days`` and
    ``restoration_financial_year``.
    """
    if application.status not in CANCELLABLE_STATUSES:
        return _blocked("not_cancellable_status")

    if (
        application.status == LeaveApplication.Status.APPROVED
        and application.start_date is not None
        and application.start_date <= get_today()
    ):
        return _blocked("leave_already_started")

    if CancellationRequest.objects.filter(
        application=application,
        status=CancellationRequest.Status.PENDING,
    ).exists():
        return _blocked("open_request_exists")

    if application.status == LeaveApplication.Status.PENDING:
        return {
            "cancellation_action": "withdraw",
            "cancellation_blocked_reason": None,
            "estimated_restoration_days": Decimal("0"),
            "restoration_financial_year": None,
        }

    stages = _workflow_provider().get_cancellation_stages(application)
    if not stages:
        return _blocked("no_cancellation_approvers")

    deduction = _balance_provider().get_deduction(application)
    return {
        "cancellation_action": "request",
        "cancellation_blocked_reason": None,
        "estimated_restoration_days": (
            deduction.days if deduction is not None else Decimal("0")
        ),
        "restoration_financial_year": (
            deduction.financial_year if deduction is not None else None
        ),
    }


def get_eligibility(application, user) -> dict:
    """Return the eligibility block for an employee's own application.

    Another employee's application raises ``ApplicationNotFoundError`` (the API
    then returns 404, never 403, so existence is not leaked).
    """
    if application.employee_id != user.id:
        raise ApplicationNotFoundError()
    return compute_cancellation_eligibility(application)


def submit_cancellation(
    *,
    user,
    application_id,
    reason,
    confirm,
    expected_action,
) -> dict:
    """Submit a withdrawal or an approved-leave cancellation request.

    Returns ``{"kind", "cancellation_request"}``. Raises the domain errors the
    API maps to HTTP responses.
    """
    with transaction.atomic():
        application = (
            LeaveApplication.objects.filter(id=application_id, employee=user)
            .select_for_update()
            .first()
        )
        if application is None:
            raise ApplicationNotFoundError()

        computed_action = compute_cancellation_eligibility(application)[
            "cancellation_action"
        ]
        if computed_action != expected_action:
            raise ActionChangedError()

        normalized = _validate_reason(reason)
        if confirm is not True:
            raise ConfirmationRequiredError()

        if computed_action == "withdraw":
            return _withdraw(application, user, normalized)

        return _create_cancellation_request(application, user, normalized)


def decide_cancellation(
    *,
    user,
    request_id,
    decision,
    comment,
    stage_version,
) -> dict:
    """Decide an approved-leave cancellation request.

    Returns ``{"application_status", "balance_restored"}``. ``decision`` is one
    of ``approve`` | ``reject``.
    """
    with transaction.atomic():
        # Lock order is always application first, then request, then stages
        # (section 3.5). Read the request un-locked to learn the application id,
        # then acquire locks strictly application -> request -> stages.
        request_row = CancellationRequest.objects.filter(id=request_id).first()
        if (
            request_row is None
            or request_row.status != CancellationRequest.Status.PENDING
        ):
            raise RequestNotPendingError()

        application = (
            LeaveApplication.objects.select_for_update()
            .filter(id=request_row.application_id)
            .first()
        )
        if application is None:
            raise ApplicationNotFoundError()

        request_row = (
            CancellationRequest.objects.select_for_update()
            .filter(id=request_id)
            .first()
        )
        if (
            request_row is None
            or request_row.status != CancellationRequest.Status.PENDING
        ):
            raise RequestNotPendingError()

        current_stage = (
            CancellationApprovalStage.objects.select_for_update()
            .filter(
                request=request_row,
                status=CancellationApprovalStage.Status.PENDING,
            )
            .order_by("order")
            .first()
        )
        if current_stage is None:
            raise RequestNotPendingError()

        if request_row.stage_version != stage_version:
            raise StaleStageVersionError()
        if current_stage.approver_id != user.id:
            raise NotCurrentApproverError()

        normalized = (comment or "").strip()
        if len(normalized) > MAX_REASON_LENGTH:
            raise CommentRequiredError()

        if decision == "reject":
            if not normalized:
                raise CommentRequiredError()
            return _reject(application, request_row, current_stage, user, normalized)

        if decision != "approve":
            raise CommentRequiredError()

        previous_status = application.status
        next_stage = (
            CancellationApprovalStage.objects.select_for_update()
            .filter(
                request=request_row,
                order__gt=current_stage.order,
            )
            .order_by("order")
            .first()
        )
        if next_stage is None:
            return _approve_final(
                application,
                request_row,
                current_stage,
                user,
                normalized,
                previous_status,
            )
        return _approve_stage(
            application,
            request_row,
            current_stage,
            next_stage,
            user,
            normalized,
        )


def _withdraw(application, user, reason: str) -> dict:
    previous_status = application.status

    request_row = CancellationRequest.objects.create(
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.WITHDRAWAL,
        reason=reason,
        status=CancellationRequest.Status.APPROVED,
        stage_version=1,
        application_status_at_request=previous_status,
        decided_at=timezone.now(),
        employee_notification_state=(
            CancellationRequest.EmployeeNotificationState.NOT_REQUIRED
        ),
    )

    application.status = LeaveApplication.Status.CANCELLED
    application.cancelled_at = timezone.now()
    application.save(
        update_fields=["status", "cancelled_at", "updated_at"]
    )

    # Close the open Unit 16 approval stage(s) so the application drops out of
    # every approver pending queue.
    ApplicationStage.objects.filter(
        application=application,
        status=ApplicationStage.Status.PENDING,
    ).update(status=ApplicationStage.Status.CANCELLED)

    _audit_and_emit(
        actor=user,
        action="cancellation.withdrawn",
        application=application,
        previous_status=previous_status,
        new_status=application.status,
        payload={
            "cancellation_request_id": str(request_row.id),
            "reason": reason,
        },
        event_name="cancellation.withdrawn",
        outcome="withdrawn",
        recipient_user_ids=[user.id],
    )

    return {
        "kind": CancellationRequest.Kind.WITHDRAWAL,
        "cancellation_request": request_row,
    }


def _create_cancellation_request(application, user, reason: str) -> dict:
    provider = _workflow_provider()
    stages = provider.get_cancellation_stages(application)
    if not stages:
        raise NoCancellationApproversError()

    request_row = CancellationRequest.objects.create(
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.APPROVED_LEAVE,
        reason=reason,
        status=CancellationRequest.Status.PENDING,
        stage_version=1,
        application_status_at_request=application.status,
    )

    for index, spec in enumerate(stages):
        CancellationApprovalStage.objects.create(
            request=request_row,
            order=spec.order,
            role=spec.role,
            role_label=_role_label(spec.role),
            approver_id=spec.approver_user_id,
            status=(
                CancellationApprovalStage.Status.PENDING
                if index == 0
                else CancellationApprovalStage.Status.WAITING
            ),
        )

    _audit_and_emit(
        actor=user,
        action="cancellation.requested",
        application=application,
        previous_status=application.status,
        new_status=application.status,
        payload={
            "cancellation_request_id": str(request_row.id),
            "reason": reason,
            "stages": [
                {"order": spec.order, "role": spec.role} for spec in stages
            ],
        },
        event_name="cancellation.requested",
        outcome="requested",
        recipient_user_ids=provider.get_workflow_member_user_ids(application),
    )

    return {
        "kind": CancellationRequest.Kind.APPROVED_LEAVE,
        "cancellation_request": request_row,
    }


def _approve_stage(
    application,
    request_row,
    current_stage,
    next_stage,
    user,
    comment: str,
) -> dict:
    current_stage.status = CancellationApprovalStage.Status.APPROVED
    current_stage.comment = comment
    current_stage.decided_at = timezone.now()
    current_stage.save(
        update_fields=["status", "comment", "decided_at"]
    )

    next_stage.status = CancellationApprovalStage.Status.PENDING
    next_stage.save(update_fields=["status"])

    request_row.stage_version += 1
    request_row.save(update_fields=["stage_version"])

    _audit_and_emit(
        actor=user,
        action="cancellation.stage_approved",
        application=application,
        previous_status=application.status,
        new_status=application.status,
        payload={
            "cancellation_request_id": str(request_row.id),
            "stage_order": current_stage.order,
        },
        event_name="cancellation.stage_approved",
        outcome="stage_approved",
        recipient_user_ids=_workflow_member_ids(application),
    )

    return {"application_status": application.status, "balance_restored": False}


def _approve_final(
    application,
    request_row,
    current_stage,
    user,
    comment: str,
    previous_status: str,
) -> dict:
    # The final approving decision re-checks the start-date guard (rule 2.1.7).
    if (
        application.start_date is not None
        and application.start_date <= get_today()
    ):
        raise LeaveAlreadyStartedError()

    current_stage.status = CancellationApprovalStage.Status.APPROVED
    current_stage.comment = comment
    current_stage.decided_at = timezone.now()
    current_stage.save(
        update_fields=["status", "comment", "decided_at"]
    )

    request_row.status = CancellationRequest.Status.APPROVED
    request_row.decided_at = timezone.now()
    request_row.employee_notification_state = (
        CancellationRequest.EmployeeNotificationState.PENDING
    )
    request_row.stage_version += 1

    application.status = LeaveApplication.Status.CANCELLED
    application.cancelled_at = timezone.now()

    balance_restored = False
    deduction = _balance_provider().get_ledger_deduction(application)
    if deduction is not None:
        restoration = _balance_provider().record_restoration(
            application=application,
            cancellation_request=request_row,
            days=deduction.days,
            financial_year=deduction.financial_year,
        )
        balance_restored = True
        request_row.balance_restored_days = restoration.days
        request_row.restored_financial_year = restoration.financial_year
        record_event(
            actor=user,
            action="balance.restored",
            target=application,
            prev_state=application.status,
            new_state=application.status,
            metadata={
                "cancellation_request_id": str(request_row.id),
                "balance_transaction_id": str(restoration.id),
                "days": str(restoration.days),
                "financial_year": restoration.financial_year,
            },
        )

    request_row.save(
        update_fields=[
            "status",
            "decided_at",
            "employee_notification_state",
            "stage_version",
            "balance_restored_days",
            "restored_financial_year",
        ]
    )
    application.save(
        update_fields=["status", "cancelled_at", "updated_at"]
    )

    _audit_and_emit(
        actor=user,
        action="cancellation.approved",
        application=application,
        previous_status=previous_status,
        new_status=application.status,
        payload={
            "cancellation_request_id": str(request_row.id),
            "balance_restored": balance_restored,
            "balance_restored_days": str(request_row.balance_restored_days),
        },
        event_name="cancellation.approved",
        outcome="approved",
        recipient_user_ids=_workflow_member_ids(application)
        + [application.employee_id],
    )

    return {
        "application_status": application.status,
        "balance_restored": balance_restored,
    }


def _reject(
    application, request_row, current_stage, user, comment: str
) -> dict:
    current_stage.status = CancellationApprovalStage.Status.REJECTED
    current_stage.comment = comment
    current_stage.decided_at = timezone.now()
    current_stage.save(
        update_fields=["status", "comment", "decided_at"]
    )

    CancellationApprovalStage.objects.filter(
        request=request_row,
        order__gt=current_stage.order,
    ).update(status=CancellationApprovalStage.Status.NOT_REACHED)

    request_row.status = CancellationRequest.Status.REJECTED
    request_row.decided_at = timezone.now()
    request_row.employee_notification_state = (
        CancellationRequest.EmployeeNotificationState.PENDING
    )
    request_row.stage_version += 1
    request_row.save(
        update_fields=[
            "status",
            "decided_at",
            "employee_notification_state",
            "stage_version",
        ]
    )

    _audit_and_emit(
        actor=user,
        action="cancellation.rejected",
        application=application,
        previous_status=application.status,
        new_status=application.status,
        payload={
            "cancellation_request_id": str(request_row.id),
            "comment": comment,
        },
        event_name="cancellation.rejected",
        outcome="rejected",
        recipient_user_ids=[application.employee_id],
    )

    return {"application_status": application.status, "balance_restored": False}


def _audit_and_emit(
    *,
    actor,
    action: str,
    application,
    previous_status: str,
    new_status: str,
    payload: dict,
    event_name: str,
    outcome: str,
    recipient_user_ids,
) -> None:
    record_event(
        actor=actor,
        action=action,
        target=application,
        prev_state=previous_status,
        new_state=new_status,
        metadata=payload,
    )
    transaction.on_commit(
        lambda: emit(
            event_name,
            {
                "application_id": str(application.id),
                "request_id": str(payload["cancellation_request_id"]),
                "outcome": outcome,
                "recipient_user_ids": recipient_user_ids,
            },
        )
    )


def _validate_reason(reason) -> str:
    normalized = (reason or "").strip()
    if len(normalized) < MIN_REASON_LENGTH:
        raise ReasonTooShortError()
    if len(normalized) > MAX_REASON_LENGTH:
        raise ReasonTooLongError()
    return normalized


def _role_label(role: str) -> str:
    from users.models import User

    try:
        return User.Role(role).label
    except ValueError:
        return role.capitalize()


def _workflow_provider():
    from workflows.providers import get_workflow_provider

    return get_workflow_provider()


def _workflow_member_ids(application) -> list[int]:
    return _workflow_provider().get_workflow_member_user_ids(application)


def get_balance_provider() -> BalanceProvider:
    """Return the balance provider (public access for views and tracking)."""
    from .fixture_balance import FixtureBalanceProvider

    return FixtureBalanceProvider()


def _balance_provider() -> BalanceProvider:
    return get_balance_provider()