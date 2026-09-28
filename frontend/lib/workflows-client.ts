import { apiErrorMessage } from "./utils";
import type { Workflow, WorkflowInput } from "./workflows";

export const WORKFLOW_CATEGORY_CODES = ["academic", "administration"] as const;

export type WorkflowCategoryCode =
  | (typeof WORKFLOW_CATEGORY_CODES)[number]
  | "";

export const WORKFLOW_CATEGORY_LABELS: Record<
  Exclude<WorkflowCategoryCode, "">,
  string
> = {
  academic: "Academic",
  administration: "Administration",
};

export const WORKFLOW_STATE_CODES = [
  "draft",
  "scheduled",
  "active",
  "inactive",
] as const;

export type WorkflowState = (typeof WORKFLOW_STATE_CODES)[number];

export const WORKFLOW_STATE_LABELS: Record<WorkflowState, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  active: "Active",
  inactive: "Inactive",
};

export function workflowCategoryLabel(
  code: WorkflowCategoryCode
): string {
  return code ? WORKFLOW_CATEGORY_LABELS[code] : "Any category";
}

export function workflowStateLabel(state: WorkflowState): string {
  return WORKFLOW_STATE_LABELS[state];
}

export function workflowStateBadgeClass(state: WorkflowState): string {
  switch (state) {
    case "active":
      return "bg-brand-secondary-subtle text-brand-secondary";
    case "scheduled":
      return "bg-brand-primary-subtle text-brand-primary";
    case "draft":
      return "bg-status-pending-subtle text-status-pending";
    case "inactive":
      return "bg-surface-muted text-text-muted";
  }
}

export async function createWorkflow(input: WorkflowInput): Promise<Workflow> {
  return proxyPost<Workflow>("/api/hr/workflows", input);
}

export async function updateWorkflow(
  id: number | string,
  input: WorkflowInput
): Promise<Workflow> {
  return proxyPatch<Workflow>(`/api/hr/workflows/${id}`, input);
}

async function proxyPost<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}

async function proxyPatch<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}