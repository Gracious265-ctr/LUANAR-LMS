"""Explicit, whitelisted serializers for the Unit 16 approvals API.

No serializer uses ``fields = "__all__"``: only the exact shapes from the spec
are returned. List items and the review payload are rendered through
:class:`Serializers` so any future change to the matrix (section 4) has one
place to land.
"""

import logging

from rest_framework import serializers

from leave.models import SupportingDocument
from leave.providers import get_provider
from leave.providers.base import LeaveBalanceUnavailableError

from .models import ApplicationStage, ApprovalDecision
from .policies import get_decision_authority, get_leave_history
from .utils import employee_profile, full_name_for, leave_type_name

logger = logging.getLogger(__name__)

CONFIGURED_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class ApprovalListItemSerializer(serializers.Serializer):
    """One row in the approvals list (pending or decided tab)."""

    def to_representation(self, application) -> dict:
        decisions = self.context.get("my_decisions_by_application", {})
        decision = decisions.get(application.id)
        profile = employee_profile(application.employee)
        return {
            "id": str(application.id),
            "reference": application.reference_number or "",
            "employee_name": full_name_for(application.employee),
            "department": profile.department if profile else "",
            "leave_type": leave_type_name(application),
            "start_date": application.start_date,
            "end_date": application.end_date,
            "working_days": application.working_days,
            "submitted_at": application.submitted_at,
            "status": application.status,
            "submission_cycle": application.submission_cycle,
            "is_resubmission": application.submission_cycle > 1,
            "my_decision": (
                None
                if decision is None
                else {"action": decision.action, "decided_at": decision.decided_at}
            ),
        }


class ApprovalDecisionInputSerializer(serializers.Serializer):
    """The decision POST body: ``{action, comment, stage_version}``."""

    action = serializers.ChoiceField(choices=ApprovalDecision.Action.choices)
    comment = serializers.CharField(required=False, allow_blank=True)
    stage_version = serializers.IntegerField(min_value=1)


class ApprovalDetailSerializer(serializers.Serializer):
    """The full review payload; rendered only after view access is granted."""

    def to_representation(self, application) -> dict:
        user = self.context["user"]
        view_access = self.context["view_access"]
        decisions = list(application.approval_decisions.all())

        authority = get_decision_authority(user, application)
        current = application.current_stage
        balance = self._balance(application)
        profile = employee_profile(application.employee)

        return {
            "id": str(application.id),
            "reference": application.reference_number or "",
            "status": application.status,
            "submission_cycle": application.submission_cycle,
            "application": {
                "leave_type": leave_type_name(application),
                "start_date": application.start_date,
                "end_date": application.end_date,
                "working_days": application.working_days,
                "reason": application.reason,
                "submitted_at": application.submitted_at,
            },
            "employee": {
                "full_name": full_name_for(application.employee),
                "staff_id": application.employee.username,
                "designation": profile.designation if profile else "",
                "department": profile.department if profile else "",
                "faculty": profile.department if profile else "",
                "grade": profile.grade if profile else "",
                "date_of_appointment": profile.appointment_date if profile else None,
            },
            "balance": balance,
            "leave_history": get_leave_history(view_access, application),
            "documents": [
                {
                    "id": str(document.id),
                    "name": document.file_name,
                    "size_bytes": document.file_size,
                    "uploaded_at": document.uploaded_at,
                }
                for document in application.documents.all()
                if document.status == SupportingDocument.Status.ACTIVE
            ],
            "decisions": [
                self._decision_entry(decision) for decision in decisions
            ],
            "resubmission": self._resubmission_block(application, decisions),
            "stages": [
                self._stage_entry(stage, _latest_decision_for(decisions, stage))
                for stage in application.stages.all()
            ],
            "current_stage": self._current_stage(application, current),
            "permissions": {
                "can_decide": authority.can_decide,
                "reason": authority.reason,
            },
            "my_stage_role_label": view_access.stage.role_label,
        }

    def _decision_entry(self, decision) -> dict:
        return {
            "cycle": decision.submission_cycle,
            "stage_order": decision.stage.stage_order,
            "role_label": decision.role_label,
            "approver_name": decision.approver_name,
            "action": decision.action,
            "comment": decision.comment,
            "decided_at": _iso(decision.decided_at),
        }

    def _resubmission_block(self, application, decisions) -> dict | None:
        if application.submission_cycle <= 1:
            return None

        revisions = list(application.revisions.order_by("revision_number"))
        latest = revisions[-1] if revisions else None

        previous_decision = _latest_decision_for(
            decisions, action_filter=("reject", "return_for_correction")
        )

        return {
            "is_resubmission": True,
            "cycle": application.submission_cycle,
            "resubmitted_at": _iso(latest.created_at) if latest else None,
            "previous_decision": (
                {
                    "role_label": previous_decision.role_label,
                    "approver_name": previous_decision.approver_name,
                    "action": previous_decision.action,
                    "comment": previous_decision.comment,
                    "decided_at": _iso(previous_decision.decided_at),
                }
                if previous_decision is not None
                else None
            ),
            "changes": latest.changes if latest else None,
            "history": [
                {
                    "cycle": revision.revision_number,
                    "resubmitted_at": _iso(revision.created_at),
                    "changes": revision.changes,
                }
                for revision in revisions
                if revision.revision_number > 1
            ],
        }

    def _balance(self, application) -> dict:
        provider = get_provider()
        try:
            balance = provider.get_leave_balance(
                application.employee_id, application.financial_year_label or ""
            )
        except LeaveBalanceUnavailableError:
            logger.warning(
                "Leave balance unavailable for employee %s (financial year %s)",
                application.employee_id,
                application.financial_year_label,
            )
            return {"entitlement": None, "used": None, "available": None}
        return {
            "entitlement": balance.entitlement,
            "used": balance.used,
            "available": balance.available,
        }

    def _stage_entry(self, stage: ApplicationStage, decision) -> dict:
        entry = {
            "order": stage.stage_order,
            "role_label": stage.role_label,
            "status": stage.status,
        }
        if decision is not None:
            entry.update(
                {
                    "approver_name": decision.approver_name,
                    "decided_at": decision.decided_at,
                    "comment": decision.comment,
                    "action": decision.action,
                }
            )
        else:
            entry.update(
                {
                    "approver_name": "",
                    "decided_at": None,
                    "comment": "",
                    "action": None,
                }
            )
        return entry

    def _current_stage(self, application, current: ApplicationStage | None) -> dict | None:
        if current is None:
            return None
        next_stage = next(
            (
                stage
                for stage in application.stages.all()
                if stage.stage_order == current.stage_order + 1
            ),
            None,
        )
        return {
            "order": current.stage_order,
            "role_label": current.role_label,
            "version": current.version,
            "is_final": current.is_final,
            "next_role_label": next_stage.role_label if next_stage else None,
        }


def _latest_decision_for(decisions, stage=None, action_filter=None):
    """Return the most recent decision, optionally filtered by stage/action."""
    candidates = decisions
    if action_filter is not None:
        candidates = [
            decision for decision in candidates if decision.action in action_filter
        ]
    if stage is not None:
        candidates = [
            decision for decision in candidates if decision.stage_id == stage.id
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda decision: (decision.decided_at, str(decision.id)))


def _iso(value):
    """Render a datetime as UTC ISO 8601 with a ``Z`` suffix."""
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")