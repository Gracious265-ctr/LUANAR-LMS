import { apiClient, apiClientUrl } from "./api-client";
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

/**
 * The active roles a chain's steps may name, read by a team's manager.
 *
 * The workflow form's role list is the same one HR reads, but the HR-only
 * reader refuses a manager, so the backend exposes a read-only list to whoever
 * manages a team (``TeamViewSet.eligible_approver_roles``). Reading it here
 * rather than through the browser proxy matters: the pages that build a chain
 * are server components, and a relative ``fetch("/api/hr/...")`` has no origin
 * to resolve against on the server — it throws, and the page then reports that
 * no role could be loaded even though every role exists.
 */
export async function listEligibleApproverRoles(): Promise<ApproverRole[]> {
  return apiClient<ApproverRole[]>("/api/v1/teams/eligible-approver-roles/");
}

export async function listRoleAssignments(
  roleId?: number | string
): Promise<RoleAssignment[]> {
  const query = roleId === undefined ? "" : `?role=${roleId}`;
  return readAllPages<RoleAssignment>(`/api/v1/role-assignments/${query}`);
}

/**
 * A role held across a whole team, by one person.
 *
 * One holder per role per team is a constraint rather than a default, so the
 * shape is deliberately the same as the institution-wide holding: the same
 * person, the same role, and only the scope differs. That is what makes the
 * three screens one pattern rather than three.
 */
export interface TeamRoleAssignment {
  id: number;
  team: number;
  role: number;
  user: number;
  user_name: string;
  role_label: string;
  /** The team's single designated manager; the flag its members run under. */
  is_team_manager: boolean;
  created_at: string;
}

/** A role held across a whole campus, reaching every team at that campus. */
export interface CampusRoleAssignment {
  id: number;
  campus: number;
  role: number;
  user: number;
  user_name: string;
  role_label: string;
  created_at: string;
}

export async function listTeamRoleAssignments(
  team?: number | string
): Promise<TeamRoleAssignment[]> {
  const query = team === undefined ? "" : `?team=${team}`;
  return readAllPages<TeamRoleAssignment>(`/api/v1/team-role-assignments/${query}`);
}

export async function listCampusRoleAssignments(
  campus?: number | string
): Promise<CampusRoleAssignment[]> {
  const query = campus === undefined ? "" : `?campus=${campus}`;
  return readAllPages<CampusRoleAssignment>(
    `/api/v1/campus-role-assignments/${query}`
  );
}
