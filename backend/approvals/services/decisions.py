"""Decisions: recording one approver decision and advancing the chain.

The execution core. :func:`decide` runs in a single transaction under a row lock
on both the application and its current stage, writes exactly one immutable
:class:`~approvals.models.ApprovalDecision`, transitions stage and application
state, and emits the approval event on commit. The optimistic ``decision_version``
check is what refuses the loser of a race with a 409 rather than letting two
people decide the same section.
"""

from django.db import transaction
from django.utils import timezone

from approvals.models import ApplicationStage, ApprovalDecision
from approvals.services.chain import notify_stage_pending
from approvals.services.reassignment import SelfApprovalBlockedError
from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication


class ApprovalNotFoundError(Exception):
    """The application does not exist or is not viewable by the approver."""


class ApprovalNotAllowedError(Exception):
    """The approver may not decide right now; carries a reason code."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ApprovalStageChangedError(Exception):
    """The stage was already decided by someone else (stale/conflict, 409)."""


class ApprovalConflictError(Exception):
    """Approving would over-subscribe the applicant's team on some day.

    A hard block enforced at every stage (UI/UX Phase 2, spec 3.2): the same
    number the team calendar flags is refused here, so a client cannot skip the
    rule. Carries the :class:`leave.conflicts.TeamConflict` that stopped it.
    """

    def __init__(self, conflict):
        self.conflict = conflict
        super().__init__("approval_conflict")


class ApprovalValidationError(ValueError):
    """Invalid action or comment; carries a dict of field errors."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _next_activatable_stage(application, decided_stage):
    """The next stage to activate after ``decided_stage`` was approved.

    The first stage above ``decided_stage`` that is still waiting. A **skipped**
    stage is never activated (Unit 30): it resolves nobody by construction, so
    activating it would strand the chain, and continuing past it is the whole
    point of having skipped it in the first place. It is still looked up under a
    row lock and its eligibility re-checked, because a stage with no one able to
    act is a chain that cannot finish and must be reported rather than activated
    as a dead end.

    Raises ``ApprovalValidationError`` when the chain simply ends or when only
    skipped stages remain, and :class:`SelfApprovalBlockedError` when the next
    stage has no eligible approver — which can only happen on a chain materialised
    before sections, where the applicant used to be skipped forward over.

    Must be called inside ``transaction.atomic()``.
    """
    remaining = list(
        ApplicationStage.objects.select_for_update()
        .filter(
            application=application,
            submission_cycle=application.workflow_chain_cycle,
            stage_order__gt=decided_stage.stage_order,
        )
        .order_by("stage_order")
    )
    if not remaining:
        raise ApprovalValidationError({"action": "Workflow chain is incomplete."})

    candidate = next(
        (
            stage
            for stage in remaining
            if stage.status == ApplicationStage.Status.WAITING
        ),
        None,
    )
    if candidate is None:
        raise ApprovalValidationError({"action": "Workflow chain is incomplete."})
    if not candidate.eligible_approvers.exists():
        raise SelfApprovalBlockedError(
            [
                "This application cannot be advanced: nobody can act on the "
                f"{candidate.role_label} stage, so there is no approver left to "
                "sign it off. An approver cannot approve their own leave "
                "application, and a mandatory section cannot be skipped. Human "
                "Resources must appoint another member of that section, or change "
                "the workflow, before this application can be decided."
            ]
        )
    return candidate


def decide(*, application_id, actor, action: str, comment: str = "", expected_version: int):
    """Record one decision and advance the application (Unit 16, spec 6.3).

    Runs in one transaction under a row lock on both the application and its
    current stage. Writes exactly one immutable :class:`ApprovalDecision`,
    transitions stage/application state, increments ``decision_version``, and
    emits the approval event on commit.

    Raises ``ApprovalNotFoundError`` (404), ``ApprovalValidationError`` (400),
    ``ApprovalNotAllowedError`` (403) or ``ApprovalStageChangedError`` (409).
    Returns the persisted application.
    """
    from chains.events import (
        APPLICATION_FINALISED,
        DECISION_RECORDED,
        ApprovalEvent,
        emit_approval_event,
    )

    if action not in ApprovalDecision.Action.values:
        raise ApprovalValidationError({"action": "Must be approve or reject."})

    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise ApprovalValidationError({"comment": "Must be at most 1000 characters."})
    if action == ApprovalDecision.Action.REJECT and not comment:
        raise ApprovalValidationError(
            {"comment": "A comment is required when rejecting."}
        )

    from chains.policies import get_decision_authority as _authority

    app = None
    with transaction.atomic():
        app = LeaveApplication.objects.select_for_update().filter(id=application_id).first()
        if app is None:
            raise ApprovalNotFoundError()

        if app.status == LeaveApplication.Status.CANCELLED:
            # Unit 18: a withdrawn or cancelled application can never be decided
            # again; surface as a conflict so clients can refresh.
            raise ApprovalStageChangedError()

        if app.current_stage_id is None:
            raise ApprovalNotAllowedError("application_closed")

        stage = (
            ApplicationStage.objects.select_for_update()
            .filter(pk=app.current_stage_id)
            .first()
        )
        # The live chain lives under ``workflow_chain_cycle`` (stages are reused
        # across resubmission cycles per Unit 17); the guard must not compare
        # against ``app.submission_cycle``, which increments on resubmission.
        if stage is None or stage.submission_cycle != app.workflow_chain_cycle:
            raise ApprovalNotAllowedError("application_closed")

        if stage.decision_version != expected_version:
            raise ApprovalStageChangedError()

        if ApprovalDecision.objects.filter(
            application=app,
            approver=actor,
            submission_cycle=app.submission_cycle,
        ).exists():
            raise ApprovalStageChangedError()

        authority = _authority(actor, app)
        if not authority.can_decide:
            raise ApprovalNotAllowedError(authority.reason or "not_current_stage")
        if stage.status != ApplicationStage.Status.PENDING:
            raise ApprovalNotAllowedError("already_decided")

        if action == ApprovalDecision.Action.APPROVE:
            # UI/UX Phase 2, spec 3.2: an approval that would leave the
            # applicant's team over-subscribed on any day is refused, at every
            # stage, from the same number the team calendar shows. Imported here
            # because ``leave.conflicts`` reaches back into leave models.
            from leave.conflicts import find_team_conflict

            conflict = find_team_conflict(app)
            if conflict is not None:
                raise ApprovalConflictError(conflict)

        before_status = app.status
        before_order = stage.stage_order
        before_version = stage.decision_version

        # Claim the stage by acting on it. A section is open to all of its
        # members, so this is the moment the stage stops being open: the
        # ``select_for_update`` above is what makes the claim exclusive, and the
        # optimistic ``decision_version`` check refuses the loser of a race with
        # 409 rather than letting two people decide the same section.
        stage.assigned_approver = actor
        app.current_approver = actor

        ApprovalDecision.objects.create(
            application=app,
            stage=stage,
            approver=actor,
            approver_name=actor.get_full_name(),
            role_label=stage.role_label,
            action=action,
            comment=comment,
            submission_cycle=app.submission_cycle,
        )

        stage.decision_version = before_version + 1
        next_stage = None
        if action == ApprovalDecision.Action.APPROVE:
            stage.status = ApplicationStage.Status.APPROVED
            if stage.is_final:
                app.status = LeaveApplication.Status.APPROVED
            else:
                next_stage = _next_activatable_stage(app, stage)
                next_stage.status = ApplicationStage.Status.PENDING
        elif action == ApprovalDecision.Action.REJECT:
            stage.status = ApplicationStage.Status.REJECTED
            app.status = LeaveApplication.Status.REJECTED
        else:
            # Only approve/reject remain (validated above).
            raise ApprovalValidationError({"action": "Must be approve or reject."})

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
            app.current_stage = next_stage
            # The spine follows the stage. The next section is open, so nobody has
            # taken it up yet and ``current_approver`` is cleared: its members
            # are read from the stage's eligibility snapshot.
            app.current_approver = None
            notify_stage_pending(next_stage, app)

        after_status = app.status
        after_order = (
            app.current_stage.stage_order
            if app.current_stage_id is not None
            else stage.stage_order
        )
        # Unit 23b (D3): stamp the final approval once, in the same save, so the
        # document can state when the leave was approved and the date can never
        # disagree with the status.
        finalised = after_status == LeaveApplication.Status.APPROVED
        if finalised and app.approved_on is None:
            app.approved_on = timezone.now()
        app.save(
            update_fields=[
                "status",
                "current_stage",
                "current_approver",
                "approved_on",
                "updated_at",
            ]
        )

        if finalised:
            # Unit 25 (D4) + Unit 23b (D8): the ledger deduction and the
            # approved-document record are both business consequences of the
            # final approval, so they are written inside this transaction and a
            # failure in either rolls the approval back. The render itself is
            # enqueued on commit, so the document is a retryable derived
            # artifact rather than part of the atomic unit.
            from leave.services.finalise import finalise_approved_application

            finalise_approved_application(app)

        record_audit(
            actor=actor,
            action=_audit_action(action),
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=app.pk,
            target_summary=app.reference_number,
            detail=changed_fields(
                {
                    "status": before_status,
                    "current_stage_order": before_order,
                    "decision_version": before_version,
                },
                {
                    "status": after_status,
                    "current_stage_order": after_order,
                    "decision_version": stage.decision_version,
                },
            ),
            reason=comment,
        )

        event = ApprovalEvent(
            kind=(
                APPLICATION_FINALISED
                if after_status == LeaveApplication.Status.APPROVED
                else DECISION_RECORDED
            ),
            application_id=str(app.pk),
            reference_number=app.reference_number or "",
            action=action,
            stage_order=stage.stage_order,
            role_label=stage.role_label,
            approver_id=actor.id,
            approver_name=actor.get_full_name(),
            comment=comment,
            submission_cycle=app.submission_cycle,
        )
        transaction.on_commit(lambda e=event: emit_approval_event(e))

    return app

def _audit_action(action: str) -> str:
    mapping = {
        ApprovalDecision.Action.APPROVE: AuditEntry.Action.APPROVED,
        ApprovalDecision.Action.REJECT: AuditEntry.Action.REJECTED,
    }
    return mapping[action]
