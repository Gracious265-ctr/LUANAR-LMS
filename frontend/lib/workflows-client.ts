import type { Workflow, WorkflowInput } from "./workflows";
import { apiErrorMessage } from "./utils";

/**
 * Build a chain for a team.
 *
 * The team is required and must be the team the chain is for: a chain created
 * here belongs to that team, and only that team may later edit it. Steps are
 * sent as the whole ordered list, so what is written is exactly what was
 * described on screen.
 */
export async function createWorkflow(input: WorkflowInput): Promise<Workflow> {
  return send<Workflow>("/api/hr/workflows", "POST", input);
}

/**
 * Edit a chain the team owns.
 *
 * `team` is accepted but must name the chain's own team — a chain cannot be
 * moved to another team, because every application already inside it would be
 * stranded at steps nobody staffs for them. The field is sent so the refusal,
 * when it comes, is the one that names the rule rather than a missing field.
 */
export async function updateWorkflow(
  id: number | string,
  input: Partial<WorkflowInput>
): Promise<Workflow> {
  return send<Workflow>(`/api/hr/workflows/${id}`, "PATCH", input);
}

async function send<T>(
  endpoint: string,
  method: "POST" | "PATCH",
  body: unknown
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(apiErrorMessage(data));
  }
  return data as T;
}
