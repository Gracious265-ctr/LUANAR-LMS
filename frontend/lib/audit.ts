import { apiClient } from "./api-client";
import type { Reassignment } from "./reassignments";

export interface AuditEntry {
  id: number;
  actor: number | null;
  actor_name: string;
  action: string;
  target_type: string;
  target_id: string;
  target_summary: string;
  /**
   * Free-form JSON. Configuration and state changes write a
   * `{"before": {...}, "after": {...}}` diff, but other actions write a flat
   * payload instead (`document_generated` records the file, `stage_skipped`
   * records the bypassed stages), so consumers must not assume the diff shape.
   */
  detail: Record<string, unknown> | null;
  reason: string;
  created_at: string;
}

export interface FinalizedApplication {
  id: string;
  reference_number: string;
  status: string;
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
}

export interface SupportingDocument {
  id: string;
  file_url: string;
  file_name: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
}

export interface ApplicationDetail extends FinalizedApplication {
  documents: SupportingDocument[];
  reassignments: Reassignment[];
  audit_entries: AuditEntry[];
}

export interface AuditEntryListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: AuditEntry[];
}

export interface FinalizedListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FinalizedApplication[];
}

export const ACTION_LABELS: Record<string, string> = {
  created: "Created",
  updated: "Updated",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
  reassigned: "Reassigned",
  submitted: "Submitted",
  application_rejection_accepted: "Rejection accepted",
  document_generated: "Approved document generated",
  document_failed: "Document generation failed",
};

export const TARGET_TYPE_LABELS: Record<string, string> = {
  employee: "Employee",
  entitlement: "Entitlement",
  leavetype: "Leave type",
  leaverule: "Leave rule",
  financialyear: "Financial year",
  publicholiday: "Public holiday",
  team: "Team",
  // A chain has no screen of its own: it is written and read through the team
  // that owns it, so its audit entries stay history rather than a link.
  workflow: "Approval chain",
  delegation: "Delegation",
  reassignment: "Reassignment",
  "document-template": "Document template",
  application: "Application",
};

export async function listAuditEntries(options: {
  action?: string;
  targetType?: string;
} = {}): Promise<AuditEntryListResponse> {
  const params = new URLSearchParams();
  if (options.action) params.set("action", options.action);
  if (options.targetType) params.set("target_type", options.targetType);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiClient<AuditEntryListResponse>(`/api/v1/audit-entries/${qs}`);
}

export async function getAuditEntry(id: number | string): Promise<AuditEntry> {
  return apiClient<AuditEntry>(`/api/v1/audit-entries/${id}/`);
}

export async function listFinalizedApplications(options: {
  employee?: string;
} = {}): Promise<FinalizedListResponse> {
  const params = new URLSearchParams();
  if (options.employee) params.set("employee", options.employee);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiClient<FinalizedListResponse>(`/api/v1/finalized-leave/${qs}`);
}

export async function getFinalizedApplication(
  id: number | string
): Promise<ApplicationDetail> {
  return apiClient<ApplicationDetail>(`/api/v1/finalized-leave/${id}/`);
}