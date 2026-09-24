import { apiClient } from "./api-client";
import type { Reassignment } from "./reassignments";

export interface AuditEntry {
  id: number;
  actor: number;
  actor_name: string;
  action: string;
  target_type: string;
  target_id: string;
  target_summary: string;
  detail: {
    before: Record<string, unknown> | null;
    after: Record<string, unknown>;
  } | null;
  reason: string;
  prev_state: string;
  new_state: string;
  created_at: string;
}

export interface FinalizedApplication {
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
}

export interface SupportingDocument {
  id: string;
  file_path: string;
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

/**
 * Human labels for the immutable action codes the audit trail records
 * (dotted codes from the backend, e.g. `leave_application.submitted` or
 * `employee.updated`). Unknown codes fall back to their raw value.
 */
export const ACTION_LABELS: Record<string, string> = {
  "leave_application.submitted": "Submitted",
  "leave_application.changes_saved": "Changes saved",
  "leave_application.approved": "Approved",
  "leave_application.rejected": "Rejected",
  "leave_application.pending_revision": "Pending revision",
  "leave_application.returned": "Returned",
  "leave_application.workflow_assigned": "Workflow assigned",
  application_resubmitted: "Resubmitted",
  resubmit: "Resubmitted",
  document_uploaded: "Document uploaded",
  document_removed: "Document removed",
  document_replaced: "Document replaced",
  cancellation_requested: "Cancellation requested",
  "balance.restored": "Balance restored",
  "employee.created": "Employee created",
  "employee.updated": "Employee updated",
  "grade_entitlement.created": "Entitlement created",
  "grade_entitlement.updated": "Entitlement updated",
  "leave_type.created": "Leave type created",
  "leave_type.updated": "Leave type updated",
  "leave_rule.created": "Leave rule created",
  "leave_rule.updated": "Leave rule updated",
  "financial_year.created": "Financial year created",
  "financial_year.updated": "Financial year updated",
  "public_holiday.created": "Holiday created",
  "public_holiday.updated": "Holiday updated",
  "workflow.created": "Workflow created",
  "workflow.updated": "Workflow updated",
  "delegation.approved": "Delegation approved",
  "delegation.rejected": "Delegation rejected",
  "delegation.cancelled": "Delegation cancelled",
  "application.reassigned": "Reassigned",
  "document_template.updated": "Template updated",
};

/**
 * Labels for the Django content-type model names surfaced as the audit
 * target (e.g. `employeeprofile`, `leavedocumenttemplate`).
 */
export const TARGET_TYPE_LABELS: Record<string, string> = {
  employeeprofile: "Employee",
  gradeentitlement: "Entitlement",
  leavetype: "Leave type",
  leaverule: "Leave rule",
  financialyear: "Financial year",
  publicholiday: "Public holiday",
  workflow: "Workflow",
  delegation: "Delegation",
  reassignment: "Reassignment",
  leavedocumenttemplate: "Document template",
  leaveapplication: "Application",
  supportingdocument: "Document",
  approvaldecision: "Decision",
  cancellationrequest: "Cancellation",
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