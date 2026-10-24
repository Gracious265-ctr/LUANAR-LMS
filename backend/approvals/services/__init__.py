"""Approvals execution: decisions, transitions, delegation, and reassignment.

Centralises approval-chain execution (decisions, stage transitions, skips), the
delegation lifecycle, and reassignment.

This package is the stable public surface; the implementation is split by
concern:

* :mod:`~approvals.services.chain` — materialising a configured chain into stages
* :mod:`~approvals.services.decisions` — recording a decision and advancing
* :mod:`~approvals.services.delegation` — the delegation request/decision lifecycle
* :mod:`~approvals.services.reassignment` — moving a pending application
* :mod:`~approvals.services.approver_identity` — who is responsible / may act

Callers keep importing from ``approvals.services`` exactly as before.
"""

from approvals.services.approver_identity import (
    acting_approver_id,
    acting_approver_identity,
    acting_approver_map,
    acting_approver_predicate,
    active_delegation_for,
    active_delegations_for_ids,
    responsible_approver_id,
)
from approvals.services.chain import (
    _initial_stage_status,
    _record_skipped_stages,
    assign_workflow,
    notify_stage_pending,
)
from approvals.services.decisions import (
    ApprovalConflictError,
    ApprovalNotAllowedError,
    ApprovalNotFoundError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    _audit_action,
    _next_activatable_stage,
    decide,
)
from approvals.services.delegation import (
    DelegationActionError,
    _lock_for_decision,
    _overlap_message,
    _record_delegation_audit,
    approve_delegation,
    cancel_delegation,
    delegation_summary,
    effective_end,
    find_conflicting_delegation,
    open_request_exists,
    reject_delegation,
    require_decision_reason,
    resolve_delegate_user,
)
from approvals.services.reassignment import (
    ReassignmentError,
    SelfApprovalBlockedError,
    is_self_approver,
    reassign_application,
    require_reassignment_reason,
)

# Names that used to leak out of the single-module version because they were
# imported at its top level. Kept re-exported so callers and patch targets that
# reach them through ``approvals.services`` keep working.
from chains.services import (
    WorkflowAssignmentError,
    _active_delegation_for_id,
    _current_stage,
    acting_approver_ids,
    eligible_approver_ids,
    user_may_act,
)

__all__ = [
    # errors
    "DelegationActionError",
    "ReassignmentError",
    "SelfApprovalBlockedError",
    "ApprovalNotFoundError",
    "ApprovalNotAllowedError",
    "ApprovalStageChangedError",
    "ApprovalConflictError",
    "ApprovalValidationError",
    # approver identity
    "active_delegation_for",
    "acting_approver_identity",
    "acting_approver_map",
    "active_delegations_for_ids",
    "responsible_approver_id",
    "acting_approver_id",
    "acting_approver_predicate",
    # delegation
    "resolve_delegate_user",
    "open_request_exists",
    "effective_end",
    "find_conflicting_delegation",
    "require_decision_reason",
    "delegation_summary",
    "_record_delegation_audit",
    "_overlap_message",
    "_lock_for_decision",
    "approve_delegation",
    "reject_delegation",
    "cancel_delegation",
    # reassignment
    "require_reassignment_reason",
    "is_self_approver",
    "reassign_application",
    # chain
    "assign_workflow",
    "_record_skipped_stages",
    "notify_stage_pending",
    "_initial_stage_status",
    # decisions
    "_next_activatable_stage",
    "decide",
    "_audit_action",
    # re-exported for compatibility
    "WorkflowAssignmentError",
    "_active_delegation_for_id",
    "_current_stage",
    "acting_approver_ids",
    "eligible_approver_ids",
    "user_may_act",
]
