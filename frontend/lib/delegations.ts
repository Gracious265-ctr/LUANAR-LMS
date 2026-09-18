import { apiClient } from "./api-client";
import type { DelegationState } from "./delegations-client";

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

export interface DelegationInput {
  approver: number;
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