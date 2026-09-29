/** Payload types matching the Unit 25 plans API (backend/plans). */

export type PlanStatus = "draft" | "submitted" | "approved" | "rejected";

export type BlockStatus =
  | "proposed"
  | "reserved"
  | "confirmed"
  | "lapsed"
  | "released";

export type StageStatus =
  | "waiting"
  | "pending"
  | "approved"
  | "rejected"
  | "skipped";

export type PlanDecisionAction = "approve" | "reject";

export type PlanScope = "mine" | "team" | "department" | "all";

export type PlanAccessScope =
  | "owner"
  | "approver"
  | "hr"
  | "peer"
  | "department";

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
  confirmation_window_start: string | null;
  confirmed_at: string | null;
  released_at: string | null;
  application_id: string | null;
  can_confirm: boolean;
  can_release: boolean;
}

export interface PlanStage {
  id: string;
  stage_order: number;
  role: string;
  role_label: string;
  assigned_approver_id: number | null;
  approver_name: string;
  status: StageStatus;
  status_label: string;
  is_final: boolean;
  decision_version: number;
}

export interface PlanDecision {
  id: string;
  stage_order: number;
  role_label: string;
  approver_name: string;
  action: PlanDecisionAction;
  comment: string;
  decided_at: string | null;
}

export interface MyDecision {
  action: PlanDecisionAction;
  stage_order: number | null;
  decided_at: string | null;
}

export interface PeerConflict {
  plan_id?: string;
  peer_name: string;
  peer_department: string;
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  overlaps_start: string | null;
  overlaps_end: string | null;
}

export interface PlanRow {
  id: string;
  period_start: string | null;
  period_end: string | null;
  financial_year_label: string | null;
  status: PlanStatus;
  status_label: string;
  submitted_at: string | null;
  decided_at: string | null;
  submission_cycle: number;
  employee_id: number;
  employee_name: string;
  block_count: number;
  working_days: number;
  blocks: PlanBlock[];
  peer_conflicts?: PeerConflict[];
}

export interface PlanListResponse {
  scope: PlanScope;
  count: number;
  results: PlanRow[];
}

export interface PlanEmployeeRef {
  id: number;
  name: string;
  department?: string;
}

export interface PlanDetail {
  meta: PlanMeta;
  employee: PlanEmployeeRef;
  blocks: PlanBlock[];
  stages: PlanStage[];
  decisions: PlanDecision[];
  access: PlanAccessScope | null;
  can_decide: boolean;
  can_submit: boolean;
  my_decision: MyDecision | null;
  peer_conflicts?: PeerConflict[];
  pending_confirmations?: PlanBlock[];
}

export interface PlanInputBlock {
  leave_type_id: number;
  start_date: string;
  end_date: string;
}

export interface PlanCreateInput {
  period_start: string;
  period_end: string;
  blocks: PlanInputBlock[];
}

export interface PlanCapabilities {
  is_approver: boolean;
  approver_pending_count: number;
  pending_confirmation_count: number;
}

export interface PendingConfirmationBlock {
  plan_id: string;
  plan_period_start: string;
  plan_period_end: string;
  id: string;
  leave_type_id: number | null;
  leave_type_code: string | null;
  leave_type_name: string | null;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  status: BlockStatus;
  status_label: string;
  confirmation_window_start: string | null;
  confirmed_at: string | null;
  released_at: string | null;
  application_id: string | null;
  can_confirm: boolean;
  can_release: boolean;
}

export interface PendingConfirmationResponse {
  count: number;
  results: PendingConfirmationBlock[];
}

export interface PlanApprovalBlockRef {
  leave_type_code: string | null;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
}

export interface PlanApprovalListItem {
  id: string;
  period_start: string | null;
  period_end: string | null;
  financial_year_label: string | null;
  status: PlanStatus;
  status_label: string;
  submitted_at: string | null;
  decided_at: string | null;
  submission_cycle: number;
  employee_name: string;
  department: string;
  stage_role_label: string;
  my_decision: MyDecision | null;
  blocks: PlanApprovalBlockRef[];
}

export interface PlanApprovalListResponse {
  tab: "pending" | "decided";
  count: number;
  next: string | null;
  previous: string | null;
  results: PlanApprovalListItem[];
}

export interface PlanApprovalDetail {
  meta: PlanMeta;
  employee: PlanEmployeeRef;
  blocks: PlanBlock[];
  stages: PlanStage[];
  decisions: PlanDecision[];
  can_decide: boolean;
  decision_version: number | null;
  my_decision: MyDecision | null;
}

export interface PlanDecisionPayload {
  action: PlanDecisionAction;
  comment?: string;
  stage_version: number;
}

export interface PlanSettings {
  confirmation_lead_days: number;
}

export interface PlanAdminListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: PlanRow[];
}

export interface PlanSubmitError {
  field: string;
  code: string;
  message: string;
  block: string | null;
}