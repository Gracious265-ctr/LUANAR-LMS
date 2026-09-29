import { apiClient } from "./api-client";
import type { WorkflowCategoryCode, WorkflowState } from "./workflows-client";

export { WORKFLOW_CATEGORY_CODES } from "./workflows-client";
export { WORKFLOW_CATEGORY_LABELS } from "./workflows-client";
export { WORKFLOW_STATE_CODES } from "./workflows-client";
export { WORKFLOW_STATE_LABELS } from "./workflows-client";
export { workflowCategoryLabel } from "./workflows-client";
export { workflowStateLabel } from "./workflows-client";
export { workflowStateBadgeClass } from "./workflows-client";

export type { WorkflowCategoryCode, WorkflowState } from "./workflows-client";

/**
 * One step of a workflow. `members` are the people who may act for it: the
 * section is decided by whichever of them acts first, so a step is not a single
 * approver but a roster with one seat taken per decision.
 */
export interface WorkflowSection {
  id: number;
  name: string;
  order: number;
  /** The role's stable code. Open-ended: HR can add roles this build never saw. */
  approver_role: string;
  /** The role's label as read, so a chain is readable without a second lookup. */
  approver_role_label: string;
  description: string;
  is_active: boolean;
  members: SectionMember[];
  member_count: number;
}

export interface SectionMember {
  id: number;
  section: number;
  section_name: string;
  section_order: number;
  workflow: number;
  approver_role: string;
  approver_role_label: string;
  user: number;
  user_name: string;
  user_email: string;
  created_at: string;
}

export interface Workflow {
  id: number;
  name: string;
  employee_category: WorkflowCategoryCode;
  department: string;
  effective_from: string | null;
  is_active: boolean;
  state: WorkflowState;
  sections: WorkflowSection[];
}

export interface WorkflowSectionInput {
  /**
   * The section's name is part of its identity: a section whose name or role
   * changes is a different step and comes back with no members, so the roster
   * is never handed to a new role without HR asking.
   */
  name: string;
  order: number;
  approver_role: string;
  description?: string;
  is_active?: boolean;
}

export interface WorkflowInput {
  name: string;
  employee_category?: WorkflowCategoryCode;
  department?: string;
  effective_from?: string | null;
  is_active?: boolean;
  sections: WorkflowSectionInput[];
}

export interface WorkflowListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Workflow[];
}

export async function listWorkflows(): Promise<WorkflowListResponse> {
  return apiClient<WorkflowListResponse>("/api/v1/workflows/");
}

export async function getWorkflow(id: number | string): Promise<Workflow> {
  return apiClient<Workflow>(`/api/v1/workflows/${id}/`);
}