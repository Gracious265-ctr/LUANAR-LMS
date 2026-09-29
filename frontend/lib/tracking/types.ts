export type TrackingStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "correction_required"
  | "cancelled";

/**
 * No `skipped` state: a section whose only member is the applicant is a
 * configuration error the backend refuses, so an application never advances
 * past a step. A step that has not been reached is `upcoming`.
 */
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

/** One active supporting document attached to the tracked application. */
export interface TrackingDocument {
  id: string;
  file_name: string;
  file_size: number;
  content_type: string;
  file_url: string;
  uploaded_at: string;
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

export type CancellationAction = "withdraw" | "request";

export interface LatestCancellation {
  id: string;
  kind: "withdrawal" | "approved_leave";
  status: "pending" | "approved" | "rejected";
  requested_at: string | null;
  decided_at: string | null;
}

export interface TrackingResponse {
  application: ApplicationSummary;
  status: TrackingStatus;
  approved_at: string | null;
  current_stage: CurrentStage | null;
  stages: TrackingStage[];
  events: TrackingEvent[];
  rejection: TrackingOutcome | null;
  correction: TrackingOutcome | null;
  resubmission: ResubmissionInfo;
  /** Unit 19 addition: the employee's active supporting documents. */
  documents: TrackingDocument[];
  /** Unit 18 additions: cancellation state appended to the same payload. */
  cancelled_at: string | null;
  cancellation_action: CancellationAction | null;
  cancellation_blocked_reason: string | null;
  has_open_cancellation_request: boolean;
  latest_cancellation: LatestCancellation | null;
}

export type TrackingResult =
  | { ok: true; data: TrackingResponse }
  | { ok: false; kind: "not_found" }
  | { ok: false; kind: "not_submitted" }
  | { ok: false; kind: "error"; message: string };