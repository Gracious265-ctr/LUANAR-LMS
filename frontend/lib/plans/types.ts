/** Payload types matching the plans API (backend/plans). */

export type PlanStatus = "draft" | "submitted" | "approved" | "rejected";

export type BlockStatus =
  | "proposed"
  | "reserved"
  | "confirmed"
  | "lapsed"
  | "released";

/**
 * No `skipped` stage: a section is never bypassed. The provider removes the
 * plan owner from the sections they belong to, so a section the owner sits in
 * is still decided by its other members, and one whose only member is the
 * owner is refused at submission rather than left pending forever.
 */
export type PlanStageStatus = "waiting" | "pending" | "approved" | "rejected";

/** Plan decisions are approve or reject only: a plan is not editable. */
export type PlanAction = "approve" | "reject";

/** Whose plans a list shows. `all` is HR-only. */
export type PlanScope = "mine" | "team" | "department" | "all";

export type PlanTab = "pending" | "decided";

/** The access the backend resolved for this caller on this plan. */
export type PlanAccessScope = "owner" | "hr" | "approver";

export interface PlanCapabilities {
  is_approver: boolean;
  approver_pending_count: number;
  pending_confirmation_count: number;
}

export interface PlanMeta {
  id: string;
  period_start: string | null;
  period_end: string | null;
  financial_year_label: string;
  status: PlanStatus;
  status_label: string;
  submitted_at: string | null;
  decided_at: string | null;
  submission_cycle: number;
}

/**
 * One block of leave inside a plan period.
 *
 * `can_confirm`/`can_release` are the backend's answer for *this* caller, so
 * the UI never has to re-derive the window rules that decide whether a block
 * is still reserved or has already started.
 */
export interface PlanBlock {
  id: string;
  leave_type_id: number | null;
  leave_type_code: string | null;
  leave_type_name: string | null;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  status: BlockStatus;
  status_label: string;
  /** When the owner must confirm by, or null when the window is not open. */
  confirmation_window_start: string | null;
  confirmed_at: string | null;
  released_at: string | null;
  /** Set once the block has become a real leave application. */
  application_id: string | null;
  can_confirm: boolean;
  can_release: boolean;
}

/** A reserved block awaiting the owner's confirmation, with its plan period. */
export interface PendingConfirmation extends PlanBlock {
  plan_id: string;
  plan_period_start: string;
  plan_period_end: string;
}

export interface PlanEmployee {
  id: number;
  name: string;
  department: string;
  team_id: number | null;
  team_name: string;
}

export interface PlanApproverRef {
  id: number;
  name: string;
}

/**
 * One section of the team's workflow.
 *
 * A section is resolved by whoever acts first, so `assigned_approver_id` is
 * null while the stage is open and the candidate snapshot is what explains
 * who may still act. The snapshot is immutable: membership changes after
 * submission do not rewrite it.
 */
export interface PlanStage {
  id: string;
  stage_order: number;
  role: string;
  role_label: string;
  role_ref_id: number | null;
  section_ref_id: number | null;
  history_scope: string | null;
  assigned_approver_id: number | null;
  approver_name: string;
  eligible_approver_ids: number[];
  eligible_approvers: PlanApproverRef[];
  is_claimed: boolean;
  status: PlanStageStatus;
  status_label: string;
  is_final: boolean;
  decision_version: number;
}

export interface PlanDecision {
  id: string;
  stage_order: number;
  role_label: string;
  approver_name: string;
  action: PlanAction;
  comment: string;
  decided_at: string | null;
}

export interface MyPlanDecision {
  action: PlanAction;
  stage_order: number;
  decided_at: string | null;
}

/**
 * A team-mate's approved block that overlaps one of the caller's own blocks.
 *
 * A warning, never an error: two people in a team can plan leave over each
 * other, but they should see it before submitting. Only approved plans'
 * reserved or confirmed future blocks are visible to peers.
 */
export interface PeerConflict {
  peer_name: string;
  peer_department: string;
  leave_type_id: number | null;
  start_date: string;
  end_date: string;
  /** The intersecting window, which may be narrower than either block. */
  overlaps_start: string;
  overlaps_end: string;
}

export interface PlanListItem extends PlanMeta {
  employee_id: number;
  employee_name: string;
  block_count: number;
  working_days: number;
  blocks: PlanBlock[];
  /** Only present on the caller's own rows: nobody else's conflicts are theirs. */
  peer_conflicts?: PeerConflict[];
}

export interface PlanListResponse {
  scope: PlanScope;
  count: number;
  results: PlanListItem[];
}

/** The owner-facing read: full blocks, the chain, and what they may do next. */
export interface PlanDetail {
  meta: PlanMeta;
  employee: PlanEmployee;
  blocks: PlanBlock[];
  stages: PlanStage[];
  decisions: PlanDecision[];
  access: PlanAccessScope | null;
  can_decide: boolean;
  can_submit: boolean;
  my_decision: MyPlanDecision | null;
  peer_conflicts?: PeerConflict[];
  pending_confirmations?: PlanBlock[];
}

/** One row of the approver queue. */
export interface PlanApprovalListItem extends PlanMeta {
  employee_name: string;
  department: string;
  team_name: string;
  stage_role_label: string;
  /** How many people may still act on the current stage. */
  stage_candidate_count: number;
  my_decision: { action: PlanAction; decided_at: string | null } | null;
  blocks: {
    leave_type_code: string | null;
    start_date: string | null;
    end_date: string | null;
    working_days: number | null;
  }[];
}

export interface PlanApprovalListResponse {
  tab: PlanTab;
  count: number;
  next: string | null;
  previous: string | null;
  results: PlanApprovalListItem[];
}

/**
 * The approver read. It carries `responsible_approver_id` — the single
 * responsible person when the chain names one, which the UI shows as "waiting
 * on" — because `can_decide` alone cannot name anybody in a candidate set.
 */
export interface PlanApprovalDetail {
  meta: PlanMeta;
  employee: PlanEmployee;
  blocks: PlanBlock[];
  stages: PlanStage[];
  decisions: PlanDecision[];
  can_decide: boolean;
  responsible_approver_id: number | null;
  decision_version: number | null;
  my_decision: MyPlanDecision | null;
}

export interface PlanBlockInput {
  leave_type_id: number;
  start_date: string;
  end_date: string;
}

export interface PlanCreateInput {
  period_start: string;
  period_end: string;
  blocks: PlanBlockInput[];
}

export interface PlanDecisionInput {
  action: PlanAction;
  comment: string;
  stage_version: number;
}

/** One validation issue from a refused submission, pinned to a block if any. */
export interface PlanValidationIssue {
  field: string;
  code: string;
  message: string;
  /** The plan block's index/id the issue belongs to, when it is block-level. */
  block: number | null;
}

export interface PlanSettings {
  confirmation_lead_days: number;
}

export interface PendingConfirmationsResponse {
  count: number;
  results: PendingConfirmation[];
}

export interface BlockStateResponse {
  status: BlockStatus;
  id: string;
}

export interface AdminListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: PlanListItem[];
}
