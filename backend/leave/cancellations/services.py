<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
from django.db import transaction
from django.utils import timezone

from workflows.models import ApplicationStage
<<<<<<< HEAD

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
=======
from workflows.policies import is_self_application

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
from .models import (
    CancellationApprovalStage,
    CancellationRequest,
    CancellationStageApprover,
)
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


class SelfDecisionError(CancellationError):
    """An approver cannot decide on their own application's cancellation (403)."""


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
    if not stages or any(not stage.approver_user_ids for stage in stages):
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
>>>>>>> feature/plans-teams


def submit_cancellation(
    *,
    user,
    application_id,
    reason,
<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
            .first()
        )
        if application is None:
            raise ApplicationNotFoundError()

<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.WITHDRAWAL,
        reason=reason,
        status=CancellationRequest.Status.APPROVED,
        stage_version=1,
<<<<<<< HEAD
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
=======
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
    if not stages_spec or any(not stage.approver_user_ids for stage in stages_spec):
        raise NoCancellationApproversError()

    if CancellationRequest.objects.filter(
        application=application,
        status=CancellationRequest.Status.PENDING,
    ).exists():
        raise OpenRequestExistsError()

    request = CancellationRequest.objects.create(
>>>>>>> feature/plans-teams
        application=application,
        requested_by=user,
        kind=CancellationRequest.Kind.APPROVED_LEAVE,
        reason=reason,
        status=CancellationRequest.Status.PENDING,
        stage_version=1,
<<<<<<< HEAD
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
                **payload,
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
=======
        requested_at=now,
        application_status_at_request=application.status,
        employee_notification_state=CancellationRequest.NotificationState.NOT_REQUIRED,
    )

    first = True
    for spec in stages_spec:
        stage = CancellationApprovalStage.objects.create(
            request=request,
            order=spec.order,
            role=spec.role,
            # The label comes from the application's own stage snapshot, so a
            # role renamed by HR after submission never rewrites this row.
            role_label=spec.role_label or spec.role,
            status=(
                CancellationApprovalStage.Status.PENDING
                if first
                else CancellationApprovalStage.Status.WAITING
            ),
        )
        CancellationStageApprover.objects.bulk_create(
            [
                CancellationStageApprover(stage=stage, user_id=user_id)
                for user_id in sorted(spec.approver_user_ids)
            ]
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
        if is_self_application(user, application):
            raise SelfDecisionError()
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
        if user.id not in stage.eligible_approver_ids():
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
    """Write an approver's decision onto a cancellation stage.

    Must be called inside ``transaction.atomic()``.
    """
    before_request = _request_state(request)
    before_stage = _stage_state(stage)

    # Acting claims the stage: the section is resolved by whoever decides
    # first, so this is the moment ``approver`` becomes known.
    stage.approver = user

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
                update_fields=[
                    "approver",
                    "status",
                    "decided_at",
                    "comment",
                    "updated_at",
                ]
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
        update_fields=[
            "approver",
            "status",
            "decided_at",
            "comment",
            "updated_at",
        ]
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
        "approver_id": stage.approver_id,
        "comment": stage.comment,
    }
>>>>>>> feature/plans-teams
