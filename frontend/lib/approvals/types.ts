/** Payload types matching the Unit 16 approvals API (backend/workflows). */

export type ApprovalAction = "approve" | "reject";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled"
  | "draft"
  | "submitted";

/**
 * `skipped` means the applicant's own position made the stage unnecessary: they
 * hold the stage, or sit above it, so it was never routed to them (Unit 30). It is
 * settled rather than outstanding, which is why it is distinct from `waiting` -- a
 * step that has not been reached yet. A step with nobody to act on at all is
 * still refused at submission.
 */
export type StageStatus =
  | "waiting"
  | "pending"
  | "approved"
  | "rejected"
  | "skipped";

export interface ApprovalCapabilities {
  is_approver: boolean;
  pending_count: number;
}

export interface LeaveTypeRef {
  id: number | null;
  code: string | null;
  name: string;
}

export interface MyDecisionRef {
  action: ApprovalAction;
  decided_at: string | null;
}

export type ApprovalTab = "pending" | "decided";

export interface ApprovalListItem {
  id: string;
  reference: string;
  employee_name: string;
  /** The employee's team *name*, or "" when they are on no team. */
  team: string;
  leave_type: LeaveTypeRef;
  start_date: string;
  end_date: string;
  working_days: number;
  submitted_at: string;
  status: ApprovalStatus;
  /**
   * The pending stage's optimistic-lock version, surfaced so a batch approval
   * can be built from the list without opening each application. Null once the
   * application has left the chain.
   */
  stage_version: number | null;
  my_decision: MyDecisionRef | null;
}

export interface ApprovalListResponse {
  tab: ApprovalTab;
  count: number;
  next: string | null;
  previous: string | null;
  results: ApprovalListItem[];
}

export interface ApplicationBlock {
  id: string;
  reference: string;
  submission_cycle: number;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  calendar_days: number;
  submitted_at: string | null;
  reason: string;
  financial_year_label: string | null;
}

export interface EmployeeBlock {
  name: string;
  designation: string;
  /** The employee's team name, or "" when they are on no team. */
  team: string;
  faculty: string;
  staff_id: string | null;
  grade: string;
  category: string;
  appointment_date: string | null;
}

export interface MinNoticeBlock {
  value: number | null;
  unit: string | null;
}

export interface RulesBlock {
  leave_type: LeaveTypeRef;
  holidays: string[];
  working_days: number;
  calendar_days: number;
  min_notice: MinNoticeBlock | null;
  requires_document: boolean;
  available_balance: number | null;
  balance_after_if_approved: number | null;
}

export interface BalanceBlock {
  entitlement: string | null;
  used: string | null;
  available: string;
  financial_year_label: string | null;
}

export interface DocumentBlock {
  id: string;
  name: string;
  size: number | null;
  content_type: string | null;
  uploaded_at: string | null;
}

export interface LeaveHistoryEntry {
  id: string;
  reference: string;
  leave_type: LeaveTypeRef;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  status: ApprovalStatus;
  submitted_at: string | null;
}

export interface AuditHistoryEntry {
  id: number;
  action: string;
  occurred_at: string;
  actor: string;
  reason: string | null;
}

export interface ApprovalStage {
  order: number;
  role: string;
  role_label: string;
  status: StageStatus;
  decision_version: number;
  assigned_approver: string;
  assigned_at: string | null;
  decided_at: string | null;
  comment: string | null;
  /** Why a `skipped` stage was passed over. Null for every other status. */
  skip_reason: string | null;
}

export interface CurrentStageBlock {
  order: number;
  role: string;
  role_label: string;
  is_final: boolean;
  next_role_label: string | null;
}

export interface DecisionBlock {
  action: ApprovalAction;
  role_label: string;
  approver_name?: string;
  comment: string | null;
  decided_at: string | null;
}

export interface WorkflowBlock {
  state: ApprovalStatus;
  current_stage: CurrentStageBlock | null;
  stages: ApprovalStage[];
  current_decision: DecisionBlock | null;
}

export interface ApprovalReview {
  application: ApplicationBlock;
  employee_info: EmployeeBlock;
  rules: RulesBlock;
  balance: BalanceBlock;
  documents: DocumentBlock[];
  history: {
    leave_history: {
      available: boolean;
      scope: string;
      entries: LeaveHistoryEntry[];
    };
    audit_history: AuditHistoryEntry[];
  };
  workflow: WorkflowBlock;
  my_decision: DecisionBlock | null;
  can_decide: boolean;
  decision_restriction: string | null;
}

export interface DecisionPayload {
  action: ApprovalAction;
  comment: string;
  stage_version: number;
}

export interface DecisionBriefing {
  status: ApprovalStatus;
  reference: string;
  current_stage: CurrentStageBlock | null;
  my_decision: DecisionBlock | null;
}

export interface DocumentDownload {
  id: string;
  name: string;
  content_type: string | null;
  size: number | null;
  download_url: string;
  document_url: string | null;
}

/** One application in a batch approval: its id and the version to guard against. */
export interface BulkApprovalItem {
  id: string;
  stage_version: number;
}

export type BulkApprovalItemStatus = "approved" | "failed";

export interface BulkApprovalItemResult {
  id: string;
  status: BulkApprovalItemStatus;
  /** Machine reason for a failure (e.g. `stage_changed`); absent on success. */
  reason?: string | null;
}

export interface BulkApprovalResponse {
  results: BulkApprovalItemResult[];
  approved: number;
  failed: number;
  limit: number;
}