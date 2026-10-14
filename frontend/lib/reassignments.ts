import { apiClient } from "./api-client";

export interface PendingApplication {
  id: string;
  reference_number: string;
  employee: number;
  employee_name: string;
  leave_type_name: string;
  start_date: string | null;
  end_date: string | null;
  calculated_days: number | null;
  reason: string;
  submitted_at: string | null;
  current_approver: number | null;
  current_approver_name: string;
  /**
   * Who actually holds the application right now: `current_approver` unless an
   * active delegation covers them, in which case their delegate. Needed because
   * reassigning to an approver who is themselves away moves the spine without
   * changing who acts.
   */
  acting_approver: number | null;
  acting_approver_name: string;
  /** True when an active delegation, not the spine, decides who acts. */
  is_delegated: boolean;
}

export interface Reassignment {
  id: number;
  application: string;
  reference_number: string;
  employee: number;
  employee_name: string;
  from_approver: number | null;
  from_approver_name: string;
  to_approver: number;
  to_approver_name: string;
  reason: string;
  decided_by: number;
  decided_by_name: string;
  created_at: string;
}

export interface ReassignmentInput {
  application: string;
  to_approver: number;
  reason: string;
}

export interface ReassignmentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Reassignment[];
}

export interface PendingListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: PendingApplication[];
}

export async function listReassignments(
  application?: string
): Promise<ReassignmentListResponse> {
  const qs = application
    ? `?application=${encodeURIComponent(application)}`
    : "";
  return apiClient<ReassignmentListResponse>(`/api/v1/reassignments/${qs}`);
}

export async function getReassignment(
  id: number | string
): Promise<Reassignment> {
  return apiClient<Reassignment>(`/api/v1/reassignments/${id}/`);
}

export async function listPendingApplications(): Promise<PendingListResponse> {
  return apiClient<PendingListResponse>("/api/v1/reassignments/pending/");
}