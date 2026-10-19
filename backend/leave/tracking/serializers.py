"""Read-only serializers for the tracking endpoint (Unit 15).

These translate the ``WorkflowTracking`` contracts (Section 2) into the API
response (Section 1). ``TrackedOutcomeSerializer`` renders the rejection
reason text under ``reason``.
"""

from rest_framework import serializers

from ..services.storage import safe_signed_document_url


class TrackedDocumentSerializer(serializers.Serializer):
    """One active supporting document attached to the tracked application.

    ``file_url`` is re-signed at read time like the employee document list,
    falling back to the stored URL when storage is not configured or the
    object is missing.
    """

    def to_representation(self, document):
        file_url = safe_signed_document_url(
            document.file_path, fallback=document.file_url
        )
        return {
            "id": str(document.id),
            "file_name": document.file_name,
            "file_size": document.file_size,
            "content_type": document.content_type,
            "file_url": file_url,
            "uploaded_at": _iso(document.uploaded_at),
        }


class TrackedApproverSerializer(serializers.Serializer):
    """Serializes the approver nested in a stage."""

    def to_representation(self, approver):
        return {
            "name": approver.name,
            "designation": approver.designation,
            "is_delegate": approver.is_delegate,
            "on_behalf_of": approver.on_behalf_of,
        }


class TrackedStageSerializer(serializers.Serializer):
    """Serializes one stage of the workflow snapshot."""

    def to_representation(self, stage):
        return {
            "order": stage.order,
            "role": stage.role,
            "role_label": stage.role_label,
            "state": stage.state,
            "approver": (
                TrackedApproverSerializer().to_representation(stage.approver)
                if stage.approver
                else None
            ),
            "assigned_at": _iso(stage.assigned_at),
            "decided_at": _iso(stage.decided_at),
            "comment": stage.comment,
            # Why a skipped stage was passed over (Unit 30). Null for every other
            # state, so a client can render the reason only where it applies.
            "skip_reason": stage.skip_reason,
        }


class TrackedEventSerializer(serializers.Serializer):
    """Serializes one activity-history entry."""

    def to_representation(self, event):
        return {
            "id": event.id,
            "type": event.type,
            "occurred_at": _iso(event.occurred_at),
            "stage_order": event.stage_order,
            "actor": event.actor,
            "comment": event.comment,
            "resubmission_number": event.resubmission_number,
        }


class TrackedOutcomeSerializer(serializers.Serializer):
    """Serializes a rejection outcome (``reason``)."""

    def to_representation(self, outcome):
        return {
            "stage_order": outcome.stage_order,
            "role_label": outcome.role_label,
            "approver_name": outcome.approver_name,
            "decided_at": _iso(outcome.decided_at),
            "reason": outcome.reason,
        }


class ResubmissionInfoSerializer(serializers.Serializer):
    """Serializes the resubmission block."""

    def to_representation(self, resubmission):
        return {
            "count": resubmission.count,
            "last_resubmitted_at": _iso(resubmission.last_resubmitted_at),
            "can_resubmit": resubmission.can_resubmit,
            "returns_to_stage": resubmission.returns_to_stage,
        }


class TrackingApplicationSerializer(serializers.Serializer):
    """Serializes the application summary block."""

    def to_representation(self, application):
        leave_type = {"id": application.leave_type_id}
        if application.rules_snapshot and application.rules_snapshot.get(
            "leave_type"
        ):
            leave_type = application.rules_snapshot["leave_type"]
        return {
            "id": str(application.id),
            "reference_number": application.reference_number,
            "leave_type": leave_type,
            "start_date": application.start_date.isoformat()
            if application.start_date
            else None,
            "end_date": application.end_date.isoformat()
            if application.end_date
            else None,
            "working_days": application.working_days,
            "submitted_at": _iso(application.submitted_at),
        }


class WorkflowTrackingSerializer(serializers.Serializer):
    """The full tracking endpoint response (Section 1)."""

    def to_representation(self, payload):
        workflow = payload.workflow
        return {
            "application": TrackingApplicationSerializer().to_representation(
                payload.application
            ),
            "status": workflow.status,
            "approved_at": _iso(workflow.approved_at),
            "current_stage": workflow.current_stage,
            "stages": [
                TrackedStageSerializer().to_representation(stage)
                for stage in workflow.stages
            ],
            "events": [
                TrackedEventSerializer().to_representation(event)
                for event in workflow.events
            ],
            "rejection": (
                TrackedOutcomeSerializer().to_representation(
                    workflow.rejection
                )
                if workflow.rejection
                else None
            ),
            "resubmission": ResubmissionInfoSerializer().to_representation(
                workflow.resubmission
            ),
            "documents": [
                TrackedDocumentSerializer().to_representation(document)
                for document in payload.application.documents.all()
            ],
            "cancelled_at": _iso(workflow.cancelled_at),
            "cancellation_action": workflow.cancellation_action,
            "cancellation_blocked_reason": workflow.cancellation_blocked_reason,
            "has_open_cancellation_request": (
                workflow.has_open_cancellation_request
            ),
            "latest_cancellation": workflow.latest_cancellation,
        }


def _iso(value):
    """Render a datetime as UTC ISO 8601 with a ``Z`` suffix (Section 1)."""
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")