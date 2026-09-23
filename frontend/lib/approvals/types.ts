export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "correction_required";

export type StageStatus =
  | "waiting"
  | "pending"
  | "approved"
  | "rejected"
  | "correction_requested";

export type DecisionAction =
  | "approve"
  | "reject"
  | "return_for_correction";

export interface Capabilities {
  is_approver: boolean;
  pending_count: number;
}

export interface ApprovalListItem {
  id: string;
  reference: string;
  employee_name: string;
  department: string;
  leave_type: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  submitted_at: string | null;
  status: ApprovalStatus;
  my_decision: { action: DecisionAction; decided_at: string } | null;
}

export interface ApprovalListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ApprovalListItem[];
}

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
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  status: ApprovalStatus;
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
}

export interface ApprovalStage {
  order: number;
  role_label: string;
  status: StageStatus;
  approver_name: string;
  decided_at: string | null;
  comment: string;
  action: DecisionAction | null;
}

export interface CurrentApprovalStage {
  version: number;
  role_label: string;
  is_final: boolean;
  next_role_label: string | null;
}

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
  stages: ApprovalStage[];
  current_stage: CurrentApprovalStage | null;
  permissions: ApprovalPermissions;
  my_stage_role_label: string;
}

export interface DecisionInput {
  action: DecisionAction;
  comment: string;
  stage_version: number;
}

export interface DocumentDownload {
  url: string;
}