import { apiClientUrl } from "./api-client";
import type { HistoryScope } from "./approver-role-scopes";

export { HISTORY_SCOPE_LABELS, HISTORY_SCOPES } from "./approver-role-scopes";
export { historyScopeLabel } from "./approver-role-scopes";
export type { HistoryScope } from "./approver-role-scopes";

export interface ApproverRole {
  id: number;
  code: string;
  label: string;
  description: string;
  is_active: boolean;
  history_scope: string;
  handles_cancellation: boolean;
  is_institution_wide: boolean;
  /** True while an active workflow, team, or holder still uses the role. */
  is_in_use: boolean;
  /** Sentences naming each blocker, so a refused retirement is actionable. */
  usage: string[];
  created_at: string;
  updated_at: string;
}

export interface ApproverRoleInput {
  /** Required on create only. The code is derived from it by the backend. */
  label?: string;
  description?: string;
  history_scope?: HistoryScope;
  handles_cancellation?: boolean;
  is_institution_wide?: boolean;
}

export interface RoleAssignment {
  id: number;
  user: number;
  user_name: string;
  role: number;
  role_label: string;
  created_at: string;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  results: T[];
}

/**
 * Read a whole paginated list, not just its first page.
 *
 * Roles and teams are reference data that a picker is built from: a page-1-only
 * read would quietly offer fewer options than the backend holds, and the
 * missing ones would look to HR like roles that do not exist.
 */
async function readAllPages<T>(endpoint: string): Promise<T[]> {
  const first = await apiClientUrl<Paginated<T>>(endpoint);
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiClientUrl<Paginated<T>>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}

export async function listApproverRoles(
  includeInactive = false
): Promise<ApproverRole[]> {
  const query = includeInactive ? "?include_inactive=1" : "";
  return readAllPages<ApproverRole>(`/api/v1/approver-roles/${query}`);
}

export async function getApproverRole(
  id: number | string
): Promise<ApproverRole> {
  return apiClientUrl<ApproverRole>(`/api/v1/approver-roles/${id}/`);
}

export async function listRoleAssignments(
  roleId?: number | string
): Promise<RoleAssignment[]> {
  const query = roleId === undefined ? "" : `?role=${roleId}`;
  return readAllPages<RoleAssignment>(`/api/v1/role-assignments/${query}`);
}
