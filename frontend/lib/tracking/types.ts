import type {
  CancellationAction,
  CancellationBlockedReason,
  CancellationRequestKind,
  CancellationRequestStatus,
  CancellationStage,
} from "@/lib/cancellation/types";

export type TrackingStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "correction_required"
  | "cancelled";

export type StageState =
  | "approved"
  | "awaiting"
  | "rejected"
  | "returned"
  | "upcoming";

export type EventType =
  | "submitted"
  | "approved"
  | "rejected"
  | "correction_requested"
  | "resubmitted"
  | "reassigned";

export interface TrackingApprover {
  name: string;
  designation: string;
  is_delegate: boolean;
  on_behalf_of: string | null;
}

export interface TrackingStage {
  order: number;
  role: string;
  role_label: string;
  state: StageState;
  approver: TrackingApprover | null;
  assigned_at: string | null;
  decided_at: string | null;
  comment: string | null;
}

export interface TrackingActor {
  name: string;
  role_label: string;
}

export interface TrackingEvent {
  id: string;
  type: string;
  occurred_at: string;
  stage_order: number | null;
  actor: TrackingActor;
  comment: string | null;
  resubmission_number: number | null;
}

export interface TrackingOutcome {
  stage_order: number;
  role_label: string;
  approver_name: string;
  decided_at: string;
  reason?: string;
  comment?: string;
}

export interface ResubmissionInfo {
  count: number;
  last_resubmitted_at: string | null;
  can_resubmit: boolean;
  returns_to_stage: { order: number; role_label: string } | null;
}

export interface ApplicationSummary {
  id: string;
  reference_number: string;
  leave_type: { id: number; name?: string };
  start_date: string;
  end_date: string;
  working_days: number;
  submitted_at: string | null;
}

export interface CurrentStage {
  order: number;
  role: string;
  role_label: string;
  approver_name: string;
  is_delegate: boolean;
  on_behalf_of: string | null;
  assigned_at: string;
}

export interface TrackingDecision {
  cycle: number;
  stage_order: number;
  role_label: string;
  approver_name: string;
  action: DecisionAction;
  comment: string;
  decided_at: string;
}

export type DecisionAction =
  | "approve"
  | "reject"
  | "return_for_correction";

export interface TrackingResubmissionEntry {
  cycle: number;
  resubmitted_at: string;
}

export interface TrackingResponse {
  application: ApplicationSummary;
  status: TrackingStatus;
  approved_at: string | null;
  submission_cycle: number;
  current_stage: CurrentStage | null;
  stages: TrackingStage[];
  events: TrackingEvent[];
  decisions: TrackingDecision[];
  resubmissions: TrackingResubmissionEntry[];
  rejection: TrackingOutcome | null;
  correction: TrackingOutcome | null;
  resubmission: ResubmissionInfo;
  cancellation_action: CancellationAction | null;
  cancellation_blocked_reason: CancellationBlockedReason | null;
  has_open_cancellation_request: boolean;
  latest_cancellation: TrackingCancellationRequest | null;
  cancelled_at: string | null;
  estimated_restoration_days: string | null;
  restoration_financial_year: string | null;
}

/** Open cancellation request summary in the tracking payload (Unit 18). */
export interface TrackingCancellationRequest {
  id: string;
  kind: CancellationRequestKind;
  status: CancellationRequestStatus;
  reason: string;
  requested_at: string | null;
  decided_at: string | null;
  stage_version: number;
  current_stage_role: string | null;
  stages: CancellationStage[];
}

export type TrackingResult =
  | { ok: true; data: TrackingResponse }
  | { ok: false; kind: "not_found" }
  | { ok: false; kind: "not_submitted" }
  | { ok: false; kind: "error"; message: string };