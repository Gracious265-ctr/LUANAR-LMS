"""Application-tracking service (Unit 15).

``get_application_tracking`` is the only access path to the read-only tracking
payload. It enforces employee ownership (404 for anyone else — never 403) and
the submitted-status gate (409 ``application_not_submitted`` for drafts), then
delegates workflow state to the configured tracking provider.

No audit records are read or written: the tracking payload is a live workflow
view with no audit-requirements (per the spec). The fixture provider performs
no database access, so ``assertNumQueries`` on the whole endpoint stays at one.
"""

from dataclasses import dataclass

from ..models import LeaveApplication
from .contracts import ResubmissionInfo, WorkflowTracking
from .provider import get_tracking_provider


class ApplicationNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class ApplicationNotSubmittedError(Exception):
    """The application is owned by the caller but has not been submitted."""


@dataclass
class TrackingPayload:
    """The application plus its workflow state, ready for serialization."""

    application: LeaveApplication
    workflow: WorkflowTracking


def get_application_tracking(user, application_id) -> TrackingPayload:
    """Return the tracking payload for ``user``'s submitted application.

    Raises ``ApplicationNotFoundError`` (404) when the application is missing or
    belongs to another employee, and ``ApplicationNotSubmittedError`` (409)
    when it is still a draft. Never raises a 403.

    Since Unit 16, submitted applications route into ``pending`` (and later
    ``approved``/``rejected``/``correction_required``) statuses, so every
    non-draft status is trackable.
    """
    application = LeaveApplication.objects.filter(
        id=application_id, employee=user
    ).first()
    if application is None:
        raise ApplicationNotFoundError()
    if application.status == LeaveApplication.Status.DRAFT:
        raise ApplicationNotSubmittedError()

    workflow = get_tracking_provider().get_workflow_tracking(application)
    workflow = _merge_real_data(workflow, application)
    return TrackingPayload(application=application, workflow=workflow)


def _merge_real_data(workflow: WorkflowTracking, application) -> WorkflowTracking:
    """Overlay the provenance the fixture scenario cannot know.

    ``submission_cycle``, the ``resubmissions`` list (from real immutable
    revisions) and ``decisions`` (real ``ApprovalDecision`` rows carrying a
    cycle) come from the database; ``can_resubmit`` comes from the real
    application status because the service already guarantees ownership (Unit
    15 rule retained). The fixture stage/event/outcome data is left untouched.
    """
    resubmissions = tuple(
        {
            "cycle": revision.revision_number,
            "resubmitted_at": revision.created_at,
        }
        for revision in application.revisions.filter(
            revision_number__gt=1
        ).order_by("revision_number")
    )

    decisions = tuple(
        {
            "cycle": decision.submission_cycle,
            "stage_order": decision.stage.stage_order,
            "role_label": decision.role_label,
            "approver_name": decision.approver_name,
            "action": decision.action,
            "comment": decision.comment,
            "decided_at": decision.decided_at,
        }
        for decision in application.approval_decisions.select_related("stage").all()
    )

    can_resubmit = application.status in (
        LeaveApplication.Status.REJECTED,
        LeaveApplication.Status.CORRECTION_REQUIRED,
    )

    resubmission = ResubmissionInfo(
        count=len(resubmissions),
        last_resubmitted_at=(
            resubmissions[-1]["resubmitted_at"]
            if resubmissions
            else workflow.resubmission.last_resubmitted_at
        ),
        can_resubmit=can_resubmit,
        returns_to_stage=workflow.resubmission.returns_to_stage,
    )

    return WorkflowTracking(
        status=workflow.status,
        approved_at=workflow.approved_at,
        current_stage=workflow.current_stage,
        stages=workflow.stages,
        events=workflow.events,
        rejection=workflow.rejection,
        correction=workflow.correction,
        resubmission=resubmission,
        submission_cycle=application.submission_cycle,
        resubmissions=resubmissions,
        decisions=decisions,
    )