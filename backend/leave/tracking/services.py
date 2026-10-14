"""Application-tracking service (Unit 15).

``get_application_tracking`` is the only access path to the read-only tracking
payload. It enforces employee ownership (404 for anyone else — never 403) and
the submitted-status gate (409 ``application_not_submitted`` for drafts), then
delegates workflow state to the configured tracking provider.

Unit 18 extends the payload with cancellation state: the real application
status wins over the fixture scenario once it leaves ``submitted`` (so a
cancelled application reports ``cancelled``), and one extra query loads the
latest cancellation request. The fixture provider's own scenario load performs
no database access, so the owner endpoint totals three queries (application,
prefetched active documents, latest cancellation).
"""

from dataclasses import dataclass, replace

<<<<<<< HEAD
from ..cancellations.services import compute_cancellation_eligibility
from ..models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveApplication,
)
from .contracts import (
    ResubmissionInfo,
    TrackedApprover,
    TrackedEvent,
    TrackedOutcome,
    TrackedStage,
    WorkflowTracking,
    _iso,
)
=======
from django.db.models import Prefetch

from ..models import LeaveApplication, SupportingDocument
from .contracts import WorkflowTracking
>>>>>>> feature/plans-teams
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
    ).prefetch_related(
        Prefetch(
            "documents",
            queryset=SupportingDocument.objects.filter(
                status=SupportingDocument.Status.ACTIVE
            ),
        )
    ).first()
    if application is None:
        raise ApplicationNotFoundError()
    if application.status == LeaveApplication.Status.DRAFT:
        raise ApplicationNotSubmittedError()

    workflow = get_tracking_provider().get_workflow_tracking(application)
<<<<<<< HEAD
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

    # Unit 18: cancellation fields (section 3.4 eligibility is live).
    open_cancellation = CancellationRequest.objects.filter(
        application=application,
        status=CancellationRequest.Status.PENDING,
    ).first()

    eligibility = compute_cancellation_eligibility(application)

    latest_cancellation = None
    if open_cancellation:
        stages = tuple(
            {
                "order": stage.order,
                "role": stage.role,
                "role_label": stage.role_label,
                "approver_name": (
                    stage.approver.get_full_name() or stage.approver.username
                    if stage.approver is not None
                    else ""
                ),
                "status": stage.status,
                "decided_at": _iso(stage.decided_at),
                "comment": stage.comment,
            }
            for stage in open_cancellation.stages.select_related("approver").all()
        )
        latest_cancellation = {
            "id": str(open_cancellation.id),
            "kind": open_cancellation.kind,
            "status": open_cancellation.status,
            "reason": open_cancellation.reason,
            "requested_at": _iso(open_cancellation.requested_at),
            "decided_at": _iso(open_cancellation.decided_at),
            "stage_version": open_cancellation.stage_version,
            "current_stage_role": next(
                (
                    stage["role_label"]
                    for stage in stages
                    if stage["status"]
                    == CancellationApprovalStage.Status.PENDING
                ),
                None,
            ),
            "stages": stages,
        }

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
        cancellation_action=eligibility["cancellation_action"],
        cancellation_blocked_reason=eligibility["cancellation_blocked_reason"],
        has_open_cancellation_request=open_cancellation is not None,
        latest_cancellation=latest_cancellation,
        cancelled_at=application.cancelled_at,
        estimated_restoration_days=eligibility["estimated_restoration_days"],
        restoration_financial_year=eligibility["restoration_financial_year"],
    )
=======

    if application.status != LeaveApplication.Status.SUBMITTED:
        workflow = replace(workflow, status=application.status)
    if application.status == LeaveApplication.Status.CANCELLED:
        workflow = replace(workflow, cancelled_at=application.cancelled_at)

    workflow = replace(workflow, **_cancellation_state(application, user))
    return TrackingPayload(application=application, workflow=workflow)


def _cancellation_state(application, user) -> dict:
    """The cancellation facts appended to every tracking payload (Unit 18).

    One query loads the latest cancellation request; the open-request flag is
    derived from it (the partial unique constraint allows at most one pending).
    Eligibility is reused from the Unit 18 service so the payload and the
    cancellation endpoints can never disagree.
    """
    from leave.cancellations.models import CancellationRequest
    from leave.cancellations.services import get_eligibility

    latest = (
        CancellationRequest.objects.filter(application=application)
        .order_by("-requested_at")
        .first()
    )
    open_request = (
        latest
        if latest is not None
        and latest.status == CancellationRequest.Status.PENDING
        else None
    )
    eligibility = get_eligibility(application, user, open_request=open_request)

    return {
        "cancellation_action": eligibility.cancellation_action,
        "cancellation_blocked_reason": eligibility.cancellation_blocked_reason,
        "has_open_cancellation_request": open_request is not None,
        "latest_cancellation": (
            {
                "id": str(latest.id),
                "kind": latest.kind,
                "status": latest.status,
                "requested_at": _z(latest.requested_at),
                "decided_at": _z(latest.decided_at),
            }
            if latest is not None
            else None
        ),
    }


def _z(value):
    """Render a datetime as UTC ISO 8601 with a ``Z`` suffix, or ``None``."""
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")
>>>>>>> feature/plans-teams
