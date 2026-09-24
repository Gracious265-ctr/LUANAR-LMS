import type { TrackingCancellationRequest } from "@/lib/tracking/types";

export type CancellationAction = "withdraw" | "request";

export type CancellationBlockedReason =
  | "not_cancellable_status"
  | "leave_already_started"
  | "open_request_exists"
  | "no_cancellation_approvers";

export type CancellationRequestStatus = "pending" | "approved" | "rejected";

export type CancellationRequestKind = "withdrawal" | "approved_leave";

export type CancellationStageStatus =
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

/** GET /api/applications/{id}/cancellation-eligibility/ */
export interface CancellationEligibility {
  cancellation_action: CancellationAction | null;
  cancellation_blocked_reason: CancellationBlockedReason | null;
  /** Shipped as a string by DRF (Decimal). */
  estimated_restoration_days: string | null;
  restoration_financial_year: string | null;
}

export interface CancellationStage {
  order: number;
  role: string;
  role_label: string;
  approver_name: string;
  status: CancellationStageStatus;
  decided_at: string | null;
  comment: string | null;
}

export interface CancellationApplicationSummary {
  reference_number: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
}

export type CancellationDecisionAction = "approved" | "rejected";

export interface MyCancellationDecision {
  action: CancellationDecisionAction;
  role_label: string;
  decided_at: string | null;
  comment?: string | null;
}

/** Item shape shared by the employee list and the approver list. */
export interface CancellationRequestSummary {
  id: string;
  kind: CancellationRequestKind;
  status: CancellationRequestStatus;
  reason: string;
  requested_at: string | null;
  decided_at: string | null;
  stage_version: number;
  balance_restored_days: string;
  restored_financial_year: string | null;
  employee_notification_state: EmployeeNotificationState;
  application_status_at_request: string;
  leave_started: boolean;
  stages: CancellationStage[];
  current_stage_role: string | null;
  application: CancellationApplicationSummary;
}

/** Row shape in the approver list (adds approver-specific fields). */
export interface CancellationApprovalListItem {
  id: string;
  kind: CancellationRequestKind;
  status: CancellationRequestStatus;
  reason: string;
  requested_at: string | null;
  decided_at: string | null;
  application_id: string;
  application_reference: string;
  employee_name: string;
  leave_type: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number;
  leave_started: boolean;
  current_stage_role: string | null;
  stage_version: number;
  my_decision: MyCancellationDecision | null;
}

export interface CancellationApprovalListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CancellationApprovalListItem[];
}

export interface CancellationBalanceImpact {
  restores_days: string;
  financial_year: string | null;
}

/** GET /api/approvals/cancellations/{request_id}/ */
export interface CancellationApprovalDetail {
  id: string;
  kind: CancellationRequestKind;
  status: CancellationRequestStatus;
  reason: string;
  requested_at: string | null;
  decided_at: string | null;
  stage_version: number;
  balance_restored_days: string;
  restored_financial_year: string | null;
  employee_notification_state: EmployeeNotificationState;
  application_status_at_request: string;
  leave_started: boolean;
  can_act: boolean;
  my_decision: MyCancellationDecision | null;
  application: {
    id: string;
    reference_number: string;
    leave_type: string;
    start_date: string | null;
    end_date: string | null;
    working_days: number;
    status: string;
  };
  balance_impact: CancellationBalanceImpact;
  stages: CancellationStage[];
}

export interface SubmitCancellationInput {
  reason: string;
  confirm: boolean;
  expected_action: CancellationAction;
}

export interface SubmitCancellationResult {
  kind: CancellationRequestKind;
  cancellation_request: { id: string; status: CancellationRequestStatus };
}

export interface CancellationDecisionInput {
  decision: "approve" | "reject";
  comment: string;
  stage_version: number;
}

export interface CancellationDecisionResult {
  application_status: string;
  balance_restored: boolean;
}

/** Additive Unit 18 fields on the Unit 15 tracking payload. */
export interface TrackingCancellation {
  cancellation_action: CancellationAction | null;
  cancellation_blocked_reason: CancellationBlockedReason | null;
  has_open_cancellation_request: boolean;
  latest_cancellation: TrackingCancellationRequest | null;
  cancelled_at: string | null;
  estimated_restoration_days: string | null;
  restoration_financial_year: string | null;
}