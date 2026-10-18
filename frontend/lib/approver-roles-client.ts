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
    // A body-less POST (the set-manager actions) must not claim to carry JSON:
    // an empty body with that content type is a malformed request to a parser
    // that is never going to be asked for the data anyway.
    ...(body === undefined
      ? {}
      : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
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
 * One manager per team: the backend clears the flag from the team's other
 * holders, so this is the "make this person the manager" action rather than a
 * toggle that could leave two. Returns the updated holding so the caller can
 * show the new state without a full re-read.
 */
export async function setTeamManager(
  id: number | string
): Promise<TeamRoleAssignment> {
  return send<TeamRoleAssignment>(
    `/api/hr/team-role-assignments/${id}/set-manager`,
    "POST"
  );
}

/** Remove the manager designation from this holding (the team keeps none). */
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
