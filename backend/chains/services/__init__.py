"""Workflow (approval-chain) configuration and team lifecycle service layer.

Owns the approval-chain builder — stage sequencing, section management, workflow
membership — and the team lifecycle (create, update, route, retire) plus roster
summaries. Chain *execution* (who may decide, delegation, reassignment) lives in
``approvals.services``; role/campus registry lives in ``organisation.services``.

This package is the stable public surface. The implementation is split by
concern so no single file has to hold the whole chain:

* :mod:`~workflows.services.configuration` — section sequencing and structure
* :mod:`~workflows.services.lifecycle` — team and workflow create/edit/route/retire
* :mod:`~workflows.services.membership` — who is appointed to what
* :mod:`~workflows.services.execution` — who may act on a pending stage
* :mod:`~workflows.services._shared` — errors, result shapes, shared helpers

Callers keep importing from ``workflows.services`` exactly as before; the names
below are re-exported from the submodule that now owns them.
"""

# Names that used to leak out of the single-module version because they were
# imported at its top level. Kept re-exported so callers that import them from
# ``workflows.services`` — as tests and the seed commands do — keep working.
from audit.services import changed_fields, record_audit
from leave.services import active_financial_year
from roles.models import ApproverRole
from roles.services import (
    WorkflowMemberError,
    _lookup_stage_role,
    _member_display_name,
    _require_hr_actor,
    _resolve_stage_role,
    create_team_role_assignment,
    is_approver_user,
    is_hr_actor,
    is_team_manager,
    role_code_from_name,
    wide_approver_ids_for_team,
)
from chains.providers import WorkflowConfigError, resolve_section_approvers
from chains.services._shared import (
    StageSequenceError,
    TeamActionError,
    TeamIssue,
    TeamReadiness,
    WorkflowActionError,
    WorkflowAssignmentError,
    _require_can_manage_team,
    _unique_team_code,
    _unique_workflow_name,
)
from chains.services.configuration import (
    ActivationIssue,
    _section_role,
    _workflow_snapshot,
    missing_approver_roles,
    normalize_section_sequence,
    replace_workflow_sections,
    workflow_section_roles,
)
from chains.services.execution import (
    _active_delegation_for_id,
    _current_stage,
    acting_approver_ids,
    eligible_approver_ids,
    user_may_act,
)
from chains.services.lifecycle import (
    _appoint_institution_wide_holder,
    _attach_section_approvers,
    _ensure_team_category,
    _place_new_team_member,
    _replace_team_chain,
    _team_snapshot,
    academic_calendar_end,
    create_team,
    create_workflow,
    deactivate_team,
    route_team,
    update_team,
    update_workflow,
    validate_team,
    wide_holder_ids,
)
from chains.services.membership import (
    _ensure_member_not_assigned_elsewhere,
    _pool_person,
    _team_member_blockers,
    _team_name,
    _workflow_team_or_error,
    add_section_member,
    assign_workflow_member,
    ensure_membership_allowed,
    ensure_not_assigned_elsewhere,
    ensure_role_consistency,
    ensure_single_stage_per_workflow,
    ensure_team_eligibility,
    remove_section_member,
    remove_team_member,
    remove_workflow_member,
    sync_workflow_members,
    team_for_section,
    team_member_summaries,
    workflow_member_pool,
)

__all__ = [
    # errors
    "WorkflowAssignmentError",
    "StageSequenceError",
    "TeamActionError",
    "WorkflowActionError",
    # result shapes
    "ActivationIssue",
    "TeamIssue",
    "TeamReadiness",
    # configuration
    "normalize_section_sequence",
    "missing_approver_roles",
    "replace_workflow_sections",
    "workflow_section_roles",
    "_section_role",
    "_workflow_snapshot",
    # execution
    "eligible_approver_ids",
    "acting_approver_ids",
    "user_may_act",
    "_current_stage",
    "_active_delegation_for_id",
    # lifecycle
    "validate_team",
    "wide_holder_ids",
    "create_team",
    "update_team",
    "route_team",
    "deactivate_team",
    "academic_calendar_end",
    "create_workflow",
    "update_workflow",
    "_ensure_team_category",
    "_appoint_institution_wide_holder",
    "_place_new_team_member",
    "_attach_section_approvers",
    "_replace_team_chain",
    "_team_snapshot",
    # membership
    "team_for_section",
    "ensure_team_eligibility",
    "ensure_role_consistency",
    "ensure_membership_allowed",
    "ensure_single_stage_per_workflow",
    "ensure_not_assigned_elsewhere",
    "add_section_member",
    "remove_section_member",
    "remove_team_member",
    "assign_workflow_member",
    "remove_workflow_member",
    "workflow_member_pool",
    "sync_workflow_members",
    "team_member_summaries",
    "_team_member_blockers",
    "_workflow_team_or_error",
    "_ensure_member_not_assigned_elsewhere",
    "_pool_person",
    "_team_name",
    # shared helpers
    "_require_can_manage_team",
    "_unique_team_code",
    "_unique_workflow_name",
    # re-exported for compatibility
    "changed_fields",
    "record_audit",
    "active_financial_year",
    "ApproverRole",
    "WorkflowMemberError",
    "_lookup_stage_role",
    "_member_display_name",
    "_require_hr_actor",
    "_resolve_stage_role",
    "create_team_role_assignment",
    "is_approver_user",
    "is_hr_actor",
    "is_team_manager",
    "role_code_from_name",
    "wide_approver_ids_for_team",
    "WorkflowConfigError",
    "resolve_section_approvers",
]
