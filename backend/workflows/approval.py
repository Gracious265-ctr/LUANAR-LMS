"""Approval decision service (Unit 16, section 5).

``decide`` is the only path that records a decision (Approve / Reject / Return
for Correction) and advances (or stops) the application workflow. It runs in
one transaction, locks the application and current stage, validates the actor
through the authority policy and the payload through the comment rules, writes
the immutable :class:`ApprovalDecision`, applies the transition table, and
fires a typed no-op domain event on commit.

No annual balance is deducted and no email is sent by any decision here
(invariant 12.4 and the Unit 16 scope boundaries).
"""

from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from leave.models import LeaveApplication

from .errors import DecisionValidationError, NotAllowed, StageChanged
from .events import ApprovalEvent, emit_approval_event
from .models import ApplicationStage, ApprovalDecision
from .policies import get_decision_authority

MAX_COMMENT_LENGTH = 1000
VALID_ACTIONS = tuple(ApprovalDecision.Action.values)


def decide(
    *,
    application_id,
    actor,
    action,
    comment,
    expected_stage_version,
) -> LeaveApplication:
    """Record a decision and apply the corresponding transition.

    Raises ``DecisionValidationError`` (400), ``NotAllowed`` (403) or
    ``StageChanged`` (409). Returns the updated application on success.
    """
    with transaction.atomic():
        application = LeaveApplication.objects.select_for_update().get(
            id=application_id
        )
        stage = _locked_current_stage(application)

        if stage.version != expected_stage_version:
            raise StageChanged()

        authority = get_decision_authority(actor, application)
        if not authority.can_decide:
            raise NotAllowed(authority.reason)

        normalized = _normalize_and_validate(action, comment)

        decision = ApprovalDecision.objects.create(
            application=application,
            stage=stage,
            approver=actor,
            approver_name=actor.get_full_name() or actor.username,
            role_label=stage.role_label,
            action=action,
            comment=normalized,
            submission_cycle=application.submission_cycle,
        )

        previous_status = application.status
        new_status = _apply_transition(
            application=application, stage=stage, action=action
        )

        record_event(
            actor=actor,
            action=f"leave_application.{action}",
            target=application,
            prev_state=previous_status,
            new_state=new_status if new_status else previous_status,
            metadata={
                "stage_order": stage.stage_order,
                "stage_version": stage.version,
                "reason": normalized,
                "decision_id": str(decision.id),
            },
        )

        transaction.on_commit(
            lambda: emit_approval_event(
                ApprovalEvent(
                    kind=_event_kind(action, stage.is_final),
                    application_id=str(application.id),
                    stage_order=stage.stage_order,
                    action=action,
                    cycle=application.submission_cycle,
                    occurred_at=timezone.now(),
                    payload={"status": application.status},
                )
            )
        )

        return application


def _locked_current_stage(application) -> ApplicationStage:
    if application.current_stage_id is None:
        raise NotAllowed("not_current_stage")
    return (
        ApplicationStage.objects.select_for_update()
        .get(id=application.current_stage_id)
    )


def _normalize_and_validate(action, comment) -> str:
    if action not in VALID_ACTIONS:
        raise DecisionValidationError(
            "action", "Action must be approve, reject or return_for_correction."
        )
    normalized = (comment or "").strip()
    if len(normalized) > MAX_COMMENT_LENGTH:
        raise DecisionValidationError(
            "comment",
            f"The comment must be at most {MAX_COMMENT_LENGTH} characters.",
        )
    if action != ApprovalDecision.Action.APPROVE and not normalized:
        raise DecisionValidationError(
            "comment",
            "A comment is required when rejecting or returning for correction.",
        )
    return normalized


def _apply_transition(*, application, stage: ApplicationStage, action: str) -> str | None:
    """Apply the section-5 transition table; return the new application status.

    ``current_stage`` is intentionally left on the decided stage for reject and
    return so the resubmission unit can return the application to it. Every
    touched stage gets ``version += 1``.
    """
    if action == ApprovalDecision.Action.APPROVE:
        stage.status = ApplicationStage.Status.APPROVED
        stage.version += 1
        stage.save(update_fields=["status", "version"])

        if stage.is_final:
            application.status = LeaveApplication.Status.APPROVED
            application.save(update_fields=["status"])
            return application.status

        next_stage = (
            ApplicationStage.objects.select_for_update().get(
                application=application,
                stage_order=stage.stage_order + 1,
            )
        )
        next_stage.status = ApplicationStage.Status.PENDING
        next_stage.version += 1
        next_stage.save(update_fields=["status", "version"])

        application.current_stage = next_stage
        application.current_approver_id = next_stage.assigned_approver_id
        application.save(update_fields=["current_stage", "current_approver"])
        return application.status

    if action == ApprovalDecision.Action.REJECT:
        stage.status = ApplicationStage.Status.REJECTED
        stage.version += 1
        stage.save(update_fields=["status", "version"])

        application.status = LeaveApplication.Status.REJECTED
        application.save(update_fields=["status"])
        return application.status

    # return_for_correction
    stage.status = ApplicationStage.Status.CORRECTION_REQUESTED
    stage.version += 1
    stage.save(update_fields=["status", "version"])

    application.status = LeaveApplication.Status.CORRECTION_REQUIRED
    application.save(update_fields=["status"])
    return application.status


def _event_kind(action: str, is_final: bool) -> str:
    if action == ApprovalDecision.Action.APPROVE and not is_final:
        return "stage_assigned"
    if action == ApprovalDecision.Action.APPROVE and is_final:
        return "application_finalised"
    return "decision_recorded"