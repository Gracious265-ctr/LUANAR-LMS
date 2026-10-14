/** Payload types matching the Unit 18 cancellation API (backend/leave/cancellations). */

export type CancellationAction = "withdraw" | "request";

export type CancellationKind = "withdrawal" | "approved_leave";

export type CancellationStatus = "pending" | "approved" | "rejected";

export type CancellationStageState =
  | "waiting"
  | "pending"
  | "approved"
  | "rejected"
  | "not_reached";

export type EmployeeNotificationState =
  | "not_required"
  | "pending"
  | "sent"
  | "failed";

export type CancellationTab = "pending" | "decided";

export interface LeaveTypeRef {
  id: number | null;
  code: string | null;
  name: string;
}

export interface CancellationEligibility {
  application_id: string;
  reference: string;
  cancellation_action: CancellationAction | null;
  cancellation_blocked_reason: string | null;
  estimated_restoration_days: string | null;
  restoration_financial_year: string | null;
  leave_started: boolean;
  starts_in_days: number | null;
}

export interface CancellationStage {
  id: string;
  order: number;
  role: string;
  role_label: string;
  status: CancellationStageState;
  approver_name: string;
  decided_at: string | null;
  comment: string | null;
}

export interface CancellationRequest {
  id: string;
  kind: CancellationKind;
  status: CancellationStatus;
  reason: string;
  requested_at: string | null;
  decided_at: string | null;
  stage_version: number;
  application_status_at_request: string;
  balance_restored_days: string;
  restored_financial_year: string | null;
  employee_notification_state: EmployeeNotificationState;
  stages: CancellationStage[];
}

export interface CancellationHistoryResponse {
  count: number;
  results: CancellationRequest[];
}

export interface SubmitCancellationPayload {
  reason: string;
  confirm: boolean;
  /** The action the dialog saw; a mismatch surfaces as ``action_changed``. */
  expected_action: CancellationAction | null;
}

export type SubmitCancellationResult =
  | { ok: true; kind: CancellationKind; request: CancellationRequest }
  | {
      ok: false;
      kind: "error";
      code: string;
      message: string;
      eligibility?: CancellationEligibility | null;
    };

export interface CancellationRow {
  request_id: string;
  application_id: string;
  reference: string;
  employee_name: string;
  leave_type: LeaveTypeRef;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  requested_at: string | null;
  current_stage_role: string | null;
  current_stage_role_label: string | null;
  stage_version: number;
  leave_started: boolean;
  starts_in_days: number | null;
}

export interface CancellationListResponse {
  tab: CancellationTab;
  count: number;
  next: string | null;
  previous: string | null;
  results: CancellationRow[];
}

export interface CancellationApplicationBlock {
  id: string;
  reference: string;
  status: string;
  leave_type: LeaveTypeRef;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  calendar_days: number;
  reason: string;
  financial_year_label: string | null;
  submitted_at: string | null;
}

export interface CancellationMyDecision {
  /** The stage status recorded for the viewer's stage. */
  decision: "approved" | "rejected";
  decided_at: string | null;
  comment: string | null;
}

export interface CancellationDetail {
  request: CancellationRequest;
  requested_by_name: string;
  stage_version: number;
  my_decision: CancellationMyDecision | null;
  can_decide: boolean;
  application: CancellationApplicationBlock;
  balance_impact: {
    restore_days: string;
    restore_financial_year: string | null;
  };
  leave_started: boolean;
}

export interface CancellationDecisionPayload {
  decision: "approve" | "reject";
  comment: string;
  stage_version: number;
}

export type CancellationDecisionResult =
  | { ok: true; data: CancellationDetail }
  | {
      ok: false;
      kind: "conflict" | "forbidden" | "validation" | "not_found" | "error";
      message: string;
      code?: string | null;
      fields?: Record<string, string>;
    };