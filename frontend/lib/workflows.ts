import { apiClient } from "./api-client";
import type {
  ApproverRoleCode,
  WorkflowCategoryCode,
  WorkflowState,
} from "./workflows-client";

export { APPROVER_ROLE_CODES } from "./workflows-client";
export { APPROVER_ROLE_LABELS } from "./workflows-client";
export { WORKFLOW_CATEGORY_CODES } from "./workflows-client";
export { WORKFLOW_CATEGORY_LABELS } from "./workflows-client";
export { WORKFLOW_STATE_CODES } from "./workflows-client";
export { WORKFLOW_STATE_LABELS } from "./workflows-client";
export { approverRoleLabel, workflowCategoryLabel } from "./workflows-client";
export { workflowStateLabel } from "./workflows-client";
export { workflowStateBadgeClass } from "./workflows-client";

export type {
  ApproverRoleCode,
  WorkflowCategoryCode,
  WorkflowState,
} from "./workflows-client";

export interface WorkflowStage {
  id: number;
  order: number;
  approver_role: ApproverRoleCode;
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
  approver_role: ApproverRoleCode;
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