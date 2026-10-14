<<<<<<< HEAD
=======
/** Payload types matching the Unit 16 approvals API (backend/workflows). */

export type ApprovalAction = "approve" | "reject" | "return_for_correction";

>>>>>>> feature/plans-teams
export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
<<<<<<< HEAD
  | "correction_required";

=======
  | "correction_required"
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
>>>>>>> feature/plans-teams
export type StageStatus =
  | "waiting"
  | "pending"
  | "approved"
  | "rejected"
<<<<<<< HEAD
  | "correction_requested";

export type DecisionAction =
  | "approve"
  | "reject"
  | "return_for_correction";

export interface Capabilities {
=======
  | "correction_requested"
  | "skipped";

export interface ApprovalCapabilities {
>>>>>>> feature/plans-teams
  is_approver: boolean;
  pending_count: number;
}

<<<<<<< HEAD
=======
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

>>>>>>> feature/plans-teams
export interface ApprovalListItem {
  id: string;
  reference: string;
  employee_name: string;
<<<<<<< HEAD
  department: string;
  leave_type: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  submitted_at: string | null;
  status: ApprovalStatus;
  submission_cycle: number;
  is_resubmission: boolean;
  my_decision: { action: DecisionAction; decided_at: string } | null;
}

export interface ApprovalListResponse {
=======
  /** The employee's team *name*, or "" when they are on no team. */
  team: string;
  leave_type: LeaveTypeRef;
  start_date: string;
  end_date: string;
  working_days: number;
  submitted_at: string;
  status: ApprovalStatus;
  my_decision: MyDecisionRef | null;
}

export interface ApprovalListResponse {
  tab: ApprovalTab;
>>>>>>> feature/plans-teams
  count: number;
  next: string | null;
  previous: string | null;
  results: ApprovalListItem[];
}

<<<<<<< HEAD
export interface ApprovalApplication {
  leave_type: string;
  start_date: string;
  end_date: string;
  working_days: number;
  reason: string;
  submitted_at: string | null;
}

export interface ApprovalEmployee {
  full_name: string;
  staff_id: string;
  designation: string;
  department: string;
  faculty: string;
  grade: string;
  date_of_appointment: string | null;
}

export interface ApprovalBalance {
  entitlement: number | null;
  used: number | null;
  available: number | null;
}

export interface LeaveHistoryItem {
  leave_type: string;
=======
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
>>>>>>> feature/plans-teams
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  status: ApprovalStatus;
<<<<<<< HEAD
}

export interface LeaveHistory {
  available: boolean;
  scope: string | null;
  items: LeaveHistoryItem[];
}

export interface ApprovalDocumentSummary {
  id: string;
  name: string;
  size_bytes: number;
  uploaded_at: string | null;
=======
  submitted_at: string | null;
}

export interface AuditHistoryEntry {
  id: number;
  action: string;
  occurred_at: string;
  actor: string;
  reason: string | null;
>>>>>>> feature/plans-teams
}

export interface ApprovalStage {
  order: number;
<<<<<<< HEAD
  role_label: string;
  status: StageStatus;
  approver_name: string;
  decided_at: string | null;
  comment: string;
  action: DecisionAction | null;
}

export interface ApprovalDecisionEntry {
  cycle: number;
  stage_order: number;
  role_label: string;
  approver_name: string;
  action: DecisionAction;
  comment: string;
  decided_at: string | null;
}

/** Change summary shapes (shared with the resubmission edit preview). */
export interface ApprovalChangeField {
  field: string;
  label: string;
  before: unknown;
  after: unknown;
}

export interface ApprovalChanges {
  has_changes: boolean;
  fields: ApprovalChangeField[];
  documents: {
    added: { name: string }[];
    removed: { name: string }[];
    replaced: { old_name: string; new_name: string }[];
  };
}

export interface ApprovalResubmission {
  is_resubmission: true;
  cycle: number;
  resubmitted_at: string | null;
  previous_decision: {
    role_label: string;
    approver_name: string;
    action: DecisionAction;
    comment: string;
    decided_at: string | null;
  } | null;
  changes: ApprovalChanges | null;
  history: {
    cycle: number;
    resubmitted_at: string | null;
    changes: ApprovalChanges | null;
  }[];
}

export interface CurrentApprovalStage {
  version: number;
=======
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
>>>>>>> feature/plans-teams
  role_label: string;
  is_final: boolean;
  next_role_label: string | null;
}

<<<<<<< HEAD
export interface ApprovalPermissions {
  can_decide: boolean;
  reason: string | null;
}

export interface ApprovalDetail {
  id: string;
  reference: string;
  status: ApprovalStatus;
  submission_cycle: number;
  application: ApprovalApplication;
  employee: ApprovalEmployee;
  balance: ApprovalBalance;
  leave_history: LeaveHistory;
  documents: ApprovalDocumentSummary[];
  decisions: ApprovalDecisionEntry[];
  resubmission: ApprovalResubmission | null;
  stages: ApprovalStage[];
  current_stage: CurrentApprovalStage | null;
  permissions: ApprovalPermissions;
  my_stage_role_label: string;
}

export interface DecisionInput {
  action: DecisionAction;
=======
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
>>>>>>> feature/plans-teams
  comment: string;
  stage_version: number;
}

<<<<<<< HEAD
export interface DocumentDownload {
  url: string;
=======
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
>>>>>>> feature/plans-teams
}