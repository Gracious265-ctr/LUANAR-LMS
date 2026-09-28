import type { Employee } from "./employees";
import { apiErrorMessage } from "./utils";
import type { Delegation, DelegationInput } from "./delegations";

export const DELEGATION_STATE_CODES = [
  "requested",
  "scheduled",
  "active",
  "ended",
  "rejected",
  "cancelled",
] as const;

export type DelegationState = (typeof DELEGATION_STATE_CODES)[number];

export const DELEGATION_STATE_LABELS: Record<DelegationState, string> = {
  requested: "Requested",
  scheduled: "Scheduled",
  active: "Active",
  ended: "Ended",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export function delegationStateLabel(state: DelegationState): string {
  return DELEGATION_STATE_LABELS[state];
}

export function delegationStateBadgeClass(state: DelegationState): string {
  switch (state) {
    case "active":
      return "bg-brand-secondary-subtle text-brand-secondary";
    case "scheduled":
      return "bg-brand-primary-subtle text-brand-primary";
    case "requested":
      return "bg-status-pending-subtle text-status-pending";
    case "rejected":
      return "bg-status-rejected-subtle text-status-rejected";
    case "cancelled":
    case "ended":
      return "bg-surface-muted text-text-muted";
  }
}

/**
 * The people who can be asked to cover or to take over an approval.
 *
 * Read from the approver holdings the API reports rather than from a list of
 * role names: a role HR adds later, or a membership a person holds under any
 * team, has to count here without a code change.
 */
export function approverRolePeople(employees: Employee[]): Employee[] {
  return employees.filter(
    (employee) => employee.is_active && employee.approver_roles.length > 0
  );
}

/**
 * Create a delegation request.
 *
 * Posts to the un-namespaced proxy: a request is normally raised by the
 * approver themselves (self-service), and only HR raises one on another's
 * behalf. The backend decides which — it forces `approver` to the caller
 * unless the caller is HR, and ignores any `approver` sent by a non-HR user.
 */
export async function createDelegation(
  input: DelegationInput
): Promise<Delegation> {
  return proxyPost<Delegation>("/api/delegations", input);
}

// The three decisions stay HR-only, so they keep the hr-namespaced proxies.
export async function approveDelegation(
  id: number | string,
  body: { delegate: number; decision_reason: string }
): Promise<Delegation> {
  return proxyPost<Delegation>(`/api/hr/delegations/${id}/approve`, body);
}

export async function rejectDelegation(
  id: number | string,
  decisionReason: string
): Promise<Delegation> {
  return proxyPost<Delegation>(`/api/hr/delegations/${id}/reject`, {
    decision_reason: decisionReason,
  });
}

export async function cancelDelegation(
  id: number | string,
  decisionReason: string
): Promise<Delegation> {
  return proxyPost<Delegation>(`/api/hr/delegations/${id}/cancel`, {
    decision_reason: decisionReason,
  });
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