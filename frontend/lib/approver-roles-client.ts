import type { ApproverRole, ApproverRoleInput, RoleAssignment } from "./approver-roles";
import { apiErrorMessage } from "./utils";

export {
  HISTORY_SCOPE_LABELS,
  HISTORY_SCOPES,
  historyScopeLabel,
} from "./approver-role-scopes";
export type { HistoryScope } from "./approver-role-scopes";

export async function createApproverRole(
  input: ApproverRoleInput
): Promise<ApproverRole> {
  return send<ApproverRole>("/api/hr/approver-roles", "POST", input);
}

export async function updateApproverRole(
  id: number | string,
  input: Partial<ApproverRoleInput>
): Promise<ApproverRole> {
  return send<ApproverRole>(`/api/hr/approver-roles/${id}`, "PATCH", input);
}

/**
 * Retire a role.
 *
 * DELETE, not a flag in the PATCH body: the backend refuses while the role is
 * still used by an active workflow, team, or holder, and answers 409 with a
 * sentence naming each blocker. That refusal is the point — it is what stops a
 * live approval chain from losing a role it still needs.
 */
export async function deactivateApproverRole(
  id: number | string
): Promise<ApproverRole> {
  return send<ApproverRole>(`/api/hr/approver-roles/${id}`, "DELETE");
}

export async function createRoleAssignment(
  input: { user: number | string; role: number | string }
): Promise<RoleAssignment> {
  return send<RoleAssignment>("/api/hr/role-assignments", "POST", input);
}

export async function removeRoleAssignment(
  id: number | string
): Promise<void> {
  await send<void>(`/api/hr/role-assignments/${id}`, "DELETE");
}

async function send<T>(
  endpoint: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) {
    return undefined as T;
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}
