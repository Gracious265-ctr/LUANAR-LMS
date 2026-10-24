import type { TeamMemberSummary, WorkflowMemberPool } from "./team-members";
import { apiErrorMessage } from "./utils";

/**
 * Read one team's roster — every employee on the team with their workflow
 * footprints — for the team members screen.
 */
export async function listTeamMembers(
  teamId: number | string
): Promise<TeamMemberSummary[]> {
  const response = await fetch(`/api/hr/teams/${teamId}/members`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.json().catch(() => ({}))));
  }
  return response.json();
}

/**
 * Place one employee on a team.
 *
 * The backend refuses an employee who is already on the team, or one with no
 * employee record, and those refusals arrive as field errors this picker can
 * show next to its input.
 */
export async function addTeamMember(
  teamId: number | string,
  userId: number
): Promise<TeamMemberSummary[]> {
  const response = await fetch(`/api/hr/teams/${teamId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user: userId }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.json().catch(() => ({}))));
  }
  return response.json();
}

/**
 * Take one employee off a team.
 *
 * A 409 names every responsibility still tying them to the team, so the
 * refusal message is a list HR can act on rather than a bare "no".
 */
export async function removeTeamMember(
  teamId: number | string,
  userId: number
): Promise<void> {
  const response = await fetch(`/api/hr/teams/${teamId}/members/${userId}`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.json().catch(() => ({}))));
  }
}

/**
 * Who may be added to a team's roster lives in `lib/teams.ts` instead: it is
 * the team *page's* server read, and a bare `/api/hr/...` fetch from a Server
 * Component carries no Authorization header, so the proxy answered 401 and the
 * caller's `catch` turned that into an empty picker. Only the writes below —
 * which run in the browser, where cookies travel — stay here.
 */

/**
 * The eligibility pool for a team's workflow memberships.
 *
 * `workflowId` scopes the answer to one of the team's own chains so its
 * current members return as already-selected; without it the answer is the
 * create-chained-screen's "who may join at all".
 */
export async function getWorkflowMemberPool(
  teamId: number | string,
  workflowId?: number | string
): Promise<WorkflowMemberPool> {
  const query = workflowId ? `?workflow=${encodeURIComponent(String(workflowId))}` : "";
  const response = await fetch(
    `/api/hr/teams/${teamId}/workflow-member-pool${query}`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.json().catch(() => ({}))));
  }
  return response.json();
}

/**
 * Take one member off a workflow's normal-member pool.
 */
export async function removeWorkflowMember(
  workflowId: number | string,
  userId: number
): Promise<void> {
  const response = await fetch(
    `/api/hr/workflows/${workflowId}/members/${userId}`,
    { method: "DELETE", cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.json().catch(() => ({}))));
  }
}