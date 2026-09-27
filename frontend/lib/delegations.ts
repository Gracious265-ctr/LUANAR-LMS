import { apiClient } from "./api-client";
import type { UserRole } from "./employees";
import { APPROVER_ROLE_CODE_SET } from "./delegations-client";
import type { DelegationState } from "./delegations-client";

export { APPROVER_ROLE_CODE_SET } from "./delegations-client";
export { DELEGATION_STATE_CODES } from "./delegations-client";
export { DELEGATION_STATE_LABELS } from "./delegations-client";
export { delegationStateLabel } from "./delegations-client";
export { delegationStateBadgeClass } from "./delegations-client";

export type { DelegationState } from "./delegations-client";

export type DelegationStatus =
  | "requested"
  | "approved"
  | "rejected"
  | "cancelled";

export interface Delegation {
  id: number;
  approver: number;
  approver_name: string;
  approver_role: string;
  delegate: number | null;
  delegate_name: string;
  starts_on: string;
  ends_on: string | null;
  request_reason: string;
  requested_by: number;
  requested_by_name: string;
  decision_reason: string;
  decided_by: number | null;
  decided_at: string | null;
  status: DelegationStatus;
  state: DelegationState;
  created_at: string;
  updated_at: string;
}

export interface DelegateCandidate {
  id: number;
  full_name: string;
  role: UserRole;
}

export interface DelegationInput {
  /** Omitted for self-service: the backend forces the authenticated user. */
  approver?: number;
  delegate?: number | null;
  starts_on: string;
  ends_on?: string | null;
  request_reason?: string;
}

export interface DelegationListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Delegation[];
}

export async function listDelegations(
  state?: DelegationState
): Promise<DelegationListResponse> {
  const qs = state ? `?state=${encodeURIComponent(state)}` : "";
  return apiClient<DelegationListResponse>(`/api/v1/delegations/${qs}`);
}

export async function getDelegation(
  id: number | string
): Promise<Delegation> {
  return apiClient<Delegation>(`/api/v1/delegations/${id}/`);
}

/**
 * Active approver-role users the caller may nominate as delegate.
 *
 * Purpose-scoped on purpose: the HR-only employee list is not opened up to
 * every approver just to fill a dropdown, so this returns only what a delegate
 * picker needs.
 */
export async function listDelegateCandidates(): Promise<DelegateCandidate[]> {
  const data = await apiClient<{ candidates: DelegateCandidate[] }>(
    "/api/v1/delegations/candidates/"
  );
  return data.candidates;
}

/** Whether this role may request cover (mirrors the backend's role set). */
export function canRequestCover(role: string | undefined | null): boolean {
  return role != null && APPROVER_ROLE_CODE_SET.has(role);
}

export interface CoverData {
  /** `null` means the list failed to load, which is distinct from "empty". */
  delegations: Delegation[] | null;
  candidates: DelegateCandidate[];
  error?: string;
}

/**
 * The approver's own delegations plus the candidate list, loaded server-side.
 *
 * Shared by the Cover tab on the approvals page and the dedicated /dashboard/cover
 * route so both entry points derive from one implementation. The list is best
 * effort: a failure degrades to a retry prompt rather than failing the whole page,
 * since a request form is still usable without the existing rows.
 */
export async function loadCoverData(): Promise<CoverData> {
  const [delegations, candidates] = await Promise.all([
    listDelegations().then(
      (response) => response.results,
      () => null
    ),
    listDelegateCandidates().catch(() => []),
  ]);

  return {
    delegations,
    candidates,
    ...(delegations === null && { error: "Could not load your delegations." }),
  };
}
