import type {
  ApproverRole,
  ApproverRoleInput,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "./approver-roles";
import { apiErrorMessage } from "./utils";

export {
  HISTORY_SCOPE_LABELS,
  HISTORY_SCOPES,
  historyScopeLabel,
} from "./approver-role-scopes";
export type { HistoryScope } from "./approver-role-scopes";

/**
 * Who holds each role institution-wide, today.
 *
 * Client-safe twin of the server-side reader in ``approver-roles.ts``: a
 * workflow form running in the browser needs to show an institution-wide
 * step's holder the moment the role is chosen, and ``approver-roles.ts`` reads
 * through ``next/headers``, which puts the server module (and its cookies
 * dependency) into the client bundle. Reads go through the ``/api/hr`` proxy,
 * so the browser only ever sees the paginated rows, never Django.
 */
export async function listRoleAssignments(
  roleId?: number | string
): Promise<RoleAssignment[]> {
  const rows: RoleAssignment[] = [];
  let page = 1;
  for (;;) {
    const params = new URLSearchParams();
    if (roleId !== undefined) {
      params.set("role", String(roleId));
    }
    params.set("page", String(page));
    const response = await fetch(`/api/hr/role-assignments/?${params}`);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(apiErrorMessage(data));
    }
    const data = (await response.json()) as {
      results?: RoleAssignment[];
      next?: string | null;
    };
    const batch = data.results ?? [];
    rows.push(...batch);
    if (!data.next || batch.length === 0) break;
    page += 1;
  }
  return rows;
}

export async function createApproverRole(
  input: ApproverRoleInput
): Promise<ApproverRole> {
  return send<ApproverRole>("/api/hr/approver-roles", "POST", input);
}

/**
 * The active roles a chain's steps may name, read by a team's manager.
 *
 * The workflow form's role list is the same one HR reads, but that reader is
 * HR-only, so a manager opening "New workflow" saw no roles and the Add-step and
 * Create-workflow buttons sat disabled — a form they could not operate. This
 * reads the read-only list the backend exposes to whoever manages a team;
 * writing roles still goes through the HR-only role endpoints.
 */
export async function listActiveApproverRoles(): Promise<ApproverRole[]> {
  const response = await fetch("/api/hr/teams/eligible-approver-roles/");
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return (await response.json()) as ApproverRole[];
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

/**
 * Give a role one holder across a whole team, replacing any existing one.
 *
 * Saving a second holder is the replacement, not an error: the screen is a
 * pick-a-role, pick-a-person form, and asking HR to delete before they may
 * change their mind is a step that only exists to satisfy the database.
 */
export async function createTeamRoleAssignment(input: {
  team: number | string;
  role: number | string;
  user: number | string;
}): Promise<TeamRoleAssignment> {
  return send<TeamRoleAssignment>(
    "/api/hr/team-role-assignments",
    "POST",
    input
  );
}

export async function removeTeamRoleAssignment(id: number | string): Promise<void> {
  await send<void>(`/api/hr/team-role-assignments/${id}`, "DELETE");
}

/**
 * Designate a team-wide holding as its team's manager.
 *
 * There is exactly one per team: the backend clears the flag from any other
 * holder on the team, so this is a selection, not an addition.
 */
export async function setTeamManager(
  id: number | string
): Promise<TeamRoleAssignment> {
  return send<TeamRoleAssignment>(
    `/api/hr/team-role-assignments/${id}/set-manager`,
    "POST"
  );
}

/** Undo a manager designation, leaving the holding in place. */
export async function clearTeamManager(
  id: number | string
): Promise<TeamRoleAssignment> {
  return send<TeamRoleAssignment>(
    `/api/hr/team-role-assignments/${id}/clear-manager`,
    "POST"
  );
}

/** The same contract as the team-wide holding, scoped to a campus. */
export async function createCampusRoleAssignment(input: {
  campus: number | string;
  role: number | string;
  user: number | string;
}): Promise<CampusRoleAssignment> {
  return send<CampusRoleAssignment>(
    "/api/hr/campus-role-assignments",
    "POST",
    input
  );
}

export async function removeCampusRoleAssignment(
  id: number | string
): Promise<void> {
  await send<void>(`/api/hr/campus-role-assignments/${id}`, "DELETE");
}
