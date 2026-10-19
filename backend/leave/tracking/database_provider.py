"""Database-backed tracking provider (Unit 21, D11/D12).

Builds a :class:`WorkflowTracking` from the real HR-track rows — the
application's ``ApplicationStage`` snapshot (chain cycle), ``ApprovalDecision``
records across cycles, ``Reassignment`` history and the submission/resubmission
``AuditEntry`` rows — so the payload, events and outcome blocks all derive from
the actual state the application passed through (invariant 12.5: stage snapshot,
never the current workflow configuration).

Event type vocabulary is pinned to the frontend ``EVENT_ICONS`` set:
``submitted``, ``approved``, ``rejected``, ``resubmitted``, ``reassigned``.
Stage states stay ``approved | awaiting | rejected | skipped | upcoming``.
"""

from datetime import datetime

from audit.models import AuditEntry
from leave.models import LeaveApplication
from approvals.models import ApplicationStage, ApprovalDecision
from approvals.models import Reassignment
from approvals.services import acting_approver_id, responsible_approver_id

from .contracts import (
    ResubmissionInfo,
    TrackedApprover,
    TrackedEvent,
    TrackedOutcome,
    TrackedStage,
    WorkflowTracking,
)
from .provider import TrackingProvider

_EVENT_TYPES = {
    ApprovalDecision.Action.APPROVE: "approved",
    ApprovalDecision.Action.REJECT: "rejected",
}


class DatabaseTrackingProvider(TrackingProvider):
    """Provider reading the real workflow tables."""

    def get_workflow_tracking(self, application) -> WorkflowTracking:
        chain_cycle = application.workflow_chain_cycle

        stages = list(
            ApplicationStage.objects.filter(
                application=application,
                submission_cycle=chain_cycle,
            )
            .select_related("assigned_approver__employee_profile")
            # One extra query for the whole chain rather than one per stage:
            # the display helpers below read the snapshot for the open stage.
            .prefetch_related("eligible_approvers")
            .order_by("stage_order")
        )
        decisions = list(
            ApprovalDecision.objects.filter(application=application)
            .select_related("approver", "stage")
            .order_by("decided_at", "id")
        )
        reassignments = list(
            Reassignment.objects.filter(application=application)
            .select_related("decided_by")
            .order_by("created_at")
        )
        audit_rows = list(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=str(application.pk),
                action__in=(
                    AuditEntry.Action.SUBMITTED,
                    AuditEntry.Action.APPLICATION_RESUBMITTED,
                ),
            ).order_by("created_at")
        )

        by_stage: dict[int, ApprovalDecision] = {}
        for decision in decisions:
            by_stage[decision.stage_id] = decision

        awaiting = next(
            (
                stage
                for stage in stages
                if stage.status == ApplicationStage.Status.PENDING
            ),
            None,
        )
        # The chain is already loaded with its snapshots, so the open stage is
        # handed to the display helpers rather than re-fetched.
        responsible_id = responsible_approver_id(application, stage=awaiting)
        acting_id = acting_approver_id(application, stage=awaiting)
        users = self._load_users(acting_id, responsible_id)

        return WorkflowTracking(
            status=(
                application.status
                if application.status != LeaveApplication.Status.SUBMITTED
                else "pending"
            ),
            approved_at=self._approved_at(application, decisions),
            current_stage=self._current_stage_block(
                application, awaiting, acting_id, responsible_id, users
            ),
            stages=tuple(
                self._stage_block(
                    stage,
                    by_stage.get(stage.pk),
                    awaiting,
                    application.submitted_at,
                    acting_id,
                    responsible_id,
                    users,
                )
                for stage in stages
            ),
            events=self._events(application, decisions, reassignments, audit_rows),
            rejection=self._outcome(
                application, ApprovalDecision.Action.REJECT, decisions
            ),
            resubmission=self._resubmission(application, audit_rows),
        )

    def _load_users(self, *user_ids) -> dict:
        ids = {user_id for user_id in user_ids if user_id is not None}
        if not ids:
            return {}
        from users.models import User

        return {
            user.pk: user
            for user in User.objects.filter(pk__in=ids).select_related(
                "employee_profile"
            )
        }

    def _stage_block(
        self,
        stage,
        decision,
        awaiting,
        submitted_at,
        acting_id,
        responsible_id,
        users,
    ) -> TrackedStage:
        state = self._stage_state(stage)
        approver = None
        assigned_at = None
        decided_at = None
        comment = None

        if stage.status == ApplicationStage.Status.PENDING and stage is awaiting:
            approver = self._acting_approver(
                acting_id, responsible_id, users
            )
            assigned_at = submitted_at
        elif decision is not None and stage.status in (
            ApplicationStage.Status.APPROVED,
            ApplicationStage.Status.REJECTED,
        ):
            approver = self._decided_approver(decision, stage)
            assigned_at = stage.created_at
            decided_at = decision.decided_at
            comment = decision.comment or None

        return TrackedStage(
            order=stage.stage_order,
            role=stage.role,
            role_label=stage.role_label,
            state=state,
            approver=approver,
            assigned_at=assigned_at,
            decided_at=decided_at,
            comment=comment,
            skip_reason=stage.skip_reason or None,
        )

    def _stage_state(self, stage) -> str:
        if stage.status == ApplicationStage.Status.APPROVED:
            return "approved"
        if stage.status == ApplicationStage.Status.PENDING:
            return "awaiting"
        if stage.status == ApplicationStage.Status.REJECTED:
            return "rejected"
        if stage.status == ApplicationStage.Status.SKIPPED:
            # A skipped stage is settled, not upcoming (Unit 30). Rendering it as
            # "upcoming" would say somebody still has to act on a stage that
            # resolves nobody -- the exact misreading the skip is meant to
            # prevent. ``WorkflowTracking`` has always allowed this state; it is
            # the frontend that has to render it.
            return "skipped"
        return "upcoming"

    def _acting_approver(self, acting_id, responsible_id, users) -> TrackedApprover | None:
        acting = users.get(acting_id) if acting_id in users else None
        if acting is None:
            return None
        is_delegate = responsible_id is not None and responsible_id != acting_id
        responsible = users.get(responsible_id) if is_delegate else None
        return TrackedApprover(
            name=_user_name(acting),
            designation=_designation(acting),
            is_delegate=is_delegate,
            on_behalf_of=_user_name(responsible),
        )

    def _decided_approver(self, decision, stage) -> TrackedApprover | None:
        is_delegate = decision.approver_id != stage.assigned_approver_id
        return TrackedApprover(
            name=decision.approver_name or _user_name(decision.approver),
            designation=_designation(decision.approver),
            is_delegate=is_delegate,
            on_behalf_of=(
                _user_name(stage.assigned_approver) if is_delegate else None
            ),
        )

    def _current_stage_block(
        self, application, awaiting, acting_id, responsible_id, users
    ) -> dict | None:
        if application.status != LeaveApplication.Status.SUBMITTED or awaiting is None:
            return None
        approver = self._acting_approver(acting_id, responsible_id, users)
        return {
            "order": awaiting.stage_order,
            "role": awaiting.role,
            "role_label": awaiting.role_label,
            "approver_name": approver.name if approver else None,
            "is_delegate": approver.is_delegate if approver else False,
            "on_behalf_of": approver.on_behalf_of if approver else None,
            "assigned_at": _z(application.submitted_at),
        }

    def _approved_at(self, application, decisions) -> datetime | None:
        if application.status != LeaveApplication.Status.APPROVED:
            return None
        final = [
            decision
            for decision in reversed(decisions)
            if decision.action == ApprovalDecision.Action.APPROVE
            and decision.stage.is_final
        ]
        return final[0].decided_at if final else None

    def _outcome(self, application, action, decisions) -> TrackedOutcome | None:
        if application.status != LeaveApplication.Status.REJECTED:
            return None
        decision = next(
            (d for d in reversed(decisions) if d.action == action),
            None,
        )
        if decision is None:
            return None
        return TrackedOutcome(
            stage_order=decision.stage.stage_order,
            role_label=decision.role_label,
            approver_name=decision.approver_name or _user_name(decision.approver),
            decided_at=decision.decided_at,
            reason=decision.comment,
        )

    def _resubmission(self, application, audit_rows) -> ResubmissionInfo:
        resubmit_rows = [
            row
            for row in audit_rows
            if row.action == AuditEntry.Action.APPLICATION_RESUBMITTED
        ]
        count = max(0, application.submission_cycle - 1)
        last_resubmitted_at = (
            resubmit_rows[-1].created_at if resubmit_rows else None
        )
        if last_resubmitted_at is None and count > 0:
            last_resubmitted_at = application.submitted_at
        can_resubmit = application.status == LeaveApplication.Status.REJECTED
        returns_to_stage = None
        if can_resubmit:
            returning = application.current_stage
            if returning is not None:
                returns_to_stage = {
                    "order": returning.stage_order,
                    "role_label": returning.role_label,
                }
        return ResubmissionInfo(
            count=count,
            last_resubmitted_at=last_resubmitted_at,
            can_resubmit=can_resubmit,
            returns_to_stage=returns_to_stage,
        )

    def _events(self, application, decisions, reassignments, audit_rows) -> tuple:
        employee_name = _user_name(application.employee)
        events = []

        submitted_row = next(
            (
                row
                for row in audit_rows
                if row.action == AuditEntry.Action.SUBMITTED
            ),
            None,
        )
        submitted_at = (
            submitted_row.created_at
            if submitted_row is not None
            else application.submitted_at
        )
        if submitted_at is not None:
            events.append(
                TrackedEvent(
                    id=f"submitted-{application.pk}",
                    type="submitted",
                    occurred_at=submitted_at,
                    stage_order=None,
                    actor={"name": employee_name or "", "role_label": "Employee"},
                    comment=None,
                    resubmission_number=None,
                )
            )

        for decision in decisions:
            event_type = _EVENT_TYPES.get(decision.action)
            if event_type is None:
                continue
            resubmission_number = (
                max(0, decision.submission_cycle - 1)
                if decision.submission_cycle > 1
                else None
            )
            events.append(
                TrackedEvent(
                    id=f"{event_type}-{decision.pk}",
                    type=event_type,
                    occurred_at=decision.decided_at,
                    stage_order=decision.stage.stage_order,
                    actor={
                        "name": decision.approver_name
                        or _user_name(decision.approver)
                        or "",
                        "role_label": decision.role_label,
                    },
                    comment=decision.comment or None,
                    resubmission_number=resubmission_number,
                )
            )

        for index, row in enumerate(audit_rows):
            if row.action != AuditEntry.Action.APPLICATION_RESUBMITTED:
                continue
            events.append(
                TrackedEvent(
                    id=f"resubmitted-{row.pk}",
                    type="resubmitted",
                    occurred_at=row.created_at,
                    stage_order=None,
                    actor={"name": employee_name or "", "role_label": "Employee"},
                    comment=None,
                    resubmission_number=index + 1,
                )
            )

        for reassignment in reassignments:
            events.append(
                TrackedEvent(
                    id=f"reassigned-{reassignment.pk}",
                    type="reassigned",
                    occurred_at=reassignment.created_at,
                    stage_order=None,
                    actor={
                        "name": _user_name(reassignment.decided_by) or "",
                        "role_label": "HR",
                    },
                    comment=reassignment.reason or None,
                    resubmission_number=None,
                )
            )

        events.sort(key=lambda event: event.occurred_at, reverse=True)
        return tuple(events)


def _user_name(user) -> str | None:
    if user is None:
        return None
    return user.get_full_name() or user.username


def _designation(user) -> str | None:
    if user is None:
        return None
    try:
        profile = user.employee_profile
    except Exception:
        return None
    return (profile.designation if profile and profile.designation else "") or None


def _z(value):
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")