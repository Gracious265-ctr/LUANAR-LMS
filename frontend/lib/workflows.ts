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

export interface WorkflowStage {
  id: number;
  order: number;
  /** The role's stable code. Open-ended: HR can add roles this build never saw. */
  approver_role: string;
  /** The role's label as read, so a chain is readable without a second lookup. */
  approver_role_label: string;
}

export interface Workflow {
  id: number;
  name: string;
  employee_category: WorkflowCategoryCode;
  department: string;
  effective_from: string | null;
  is_active: boolean;
  state: WorkflowState;
  stages: WorkflowStage[];
}

export interface WorkflowStageInput {
  order: number;
  approver_role: string;
}

export interface WorkflowInput {
  name: string;
  employee_category?: WorkflowCategoryCode;
  department?: string;
  effective_from?: string | null;
  is_active?: boolean;
  stages: WorkflowStageInput[];
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