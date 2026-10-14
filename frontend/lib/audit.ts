import { apiClient } from "./api-client";
import type { Reassignment } from "./reassignments";

export interface AuditEntry {
  id: number;
<<<<<<< HEAD
  actor: number;
=======
  actor: number | null;
>>>>>>> feature/plans-teams
  actor_name: string;
  action: string;
  target_type: string;
  target_id: string;
  target_summary: string;
<<<<<<< HEAD
  detail: {
    before: Record<string, unknown> | null;
    after: Record<string, unknown>;
  } | null;
  reason: string;
  prev_state: string;
  new_state: string;
=======
  /**
   * Free-form JSON. Configuration and state changes write a
   * `{"before": {...}, "after": {...}}` diff, but other actions write a flat
   * payload instead (`document_generated` records the file, `stage_skipped`
   * records the bypassed stages), so consumers must not assume the diff shape.
   */
  detail: Record<string, unknown> | null;
  reason: string;
>>>>>>> feature/plans-teams
  created_at: string;
}

export interface FinalizedApplication {
  id: string;
  reference_number: string;
<<<<<<< HEAD
=======
  status: string;
>>>>>>> feature/plans-teams
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
<<<<<<< HEAD
  file_path: string;
=======
>>>>>>> feature/plans-teams
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

<<<<<<< HEAD
/**
 * Human labels for the immutable action codes the audit trail records
 * (dotted codes from the backend, e.g. `leave_application.submitted` or
 * `employee.updated`). Unknown codes fall back to their raw value.
 */
export const ACTION_LABELS: Record<string, string> = {
  "leave_application.submitted": "Submitted",
  "leave_application.changes_saved": "Changes saved",
  "leave_application.approved": "Approved",
  "leave_application.approve": "Approved",
  "leave_application.rejected": "Rejected",
  "leave_application.reject": "Rejected",
  "leave_application.pending_revision": "Pending revision",
  "leave_application.returned": "Returned",
  "leave_application.return_for_correction": "Returned for correction",
  "leave_application.workflow_assigned": "Workflow assigned",
  application_resubmitted: "Resubmitted",
  resubmit: "Resubmitted",
  document_uploaded: "Document uploaded",
  document_removed: "Document removed",
  document_replaced: "Document replaced",
  cancellation_requested: "Cancellation requested",
  "cancellation.withdrawn": "Withdrawn",
  "cancellation.requested": "Cancellation requested",
  "cancellation.stage_approved": "Cancellation stage approved",
  "cancellation.approved": "Cancellation approved",
  "cancellation.rejected": "Cancellation rejected",
  "balance.restored": "Balance restored",
  "balance.deducted": "Days deducted from balance",
  "approved_document.generated": "Approval document generated",
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
=======
export const ACTION_LABELS: Record<string, string> = {
  created: "Created",
  updated: "Updated",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
  reassigned: "Reassigned",
  submitted: "Submitted",
  document_generated: "Approved document generated",
  document_failed: "Document generation failed",
  plan_submitted: "Plan submitted",
  plan_approved: "Plan approved",
  plan_rejected: "Plan rejected",
  plan_confirmed: "Plan block confirmed",
  plan_released: "Plan block released",
};

export const TARGET_TYPE_LABELS: Record<string, string> = {
  employee: "Employee",
  entitlement: "Entitlement",
>>>>>>> feature/plans-teams
  leavetype: "Leave type",
  leaverule: "Leave rule",
  financialyear: "Financial year",
  publicholiday: "Public holiday",
<<<<<<< HEAD
  workflow: "Workflow",
  delegation: "Delegation",
  reassignment: "Reassignment",
  leavedocumenttemplate: "Document template",
  leaveapplication: "Application",
  supportingdocument: "Document",
  approvaldecision: "Decision",
  cancellationrequest: "Cancellation",
=======
  team: "Team",
  // A chain has no screen of its own: it is written and read through the team
  // that owns it, so its audit entries stay history rather than a link.
  workflow: "Approval chain",
  delegation: "Delegation",
  reassignment: "Reassignment",
  "document-template": "Document template",
  application: "Application",
  plan: "Leave day plan",
>>>>>>> feature/plans-teams
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