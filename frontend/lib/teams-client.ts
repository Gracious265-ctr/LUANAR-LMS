import type {
  Campus,
  CampusInput,
  EligibleApprover,
  Team,
  TeamInput,
  TeamReadiness,
  TeamStatus,
} from "./teams";
import type { Employee } from "./employees";
import { apiErrorMessage } from "./utils";

export const TEAM_STATUS_LABELS: Record<TeamStatus, string> = {
  draft: "Draft",
  active: "Active",
  inactive: "Retired",
};

export function teamStatusLabel(status: string): string {
  return TEAM_STATUS_LABELS[status as TeamStatus] ?? status;
}

/**
 * The shared `Badge` `tone` for a team status, so the pill renders through the
 * one status→colour mapping instead of restating classes.
 */
export function teamStatusBadgeTone(
  status: string
): "info" | "muted" | "pending" {
  switch (status) {
    case "active":
      return "info";
    case "inactive":
      return "muted";
    default:
      return "pending";
  }
}

/**
 * The people who may be appointed to a team's approval steps, scoped to the
 * team itself and optionally to the step's role.
 *
 * Fetched from the backend rather than filtered in the browser because
 * eligibility *is* the team: a picker built from the whole staff would offer
 * people the write then refuses. The role narrowing is the same idea — one
 * person holds one role per team, so the list is only the people who can pass
 * that.
 *
 * ``workflow`` scopes the pool to one of the team's own chains, so people who
 * already serve a *different* chain of the team (as a step approver or as a
 * normal member) are dropped — one employee serves one chain. Use the chain's
 * id when editing it, or the sentinel ``"new"`` when configuring one that does
 * not exist yet.
 */
export async function listEligibleApprovers(
  team: number,
  role?: number,
  workflow?: number | "new"
): Promise<EligibleApprover[]> {
  const params = new URLSearchParams({ team: String(team) });
  if (role !== undefined) {
    params.set("role", String(role));
  }
  if (workflow !== undefined) {
    params.set("workflow", String(workflow));
  }
  const response = await fetch(
    `/api/hr/teams/eligible-approvers/?${params.toString()}`
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  const data = (await response.json()) as { candidates?: EligibleApprover[] };
  return data.candidates ?? [];
}

/**
 * The people who may be placed on a team's roster, read by the team itself.
 *
 * The same list HR reads from the employee directory (`?team=none&category=…`,
 * minus its wide approvers), but through a route a team's manager may reach: the
 * directory is HR-only, so a manager building their roster could otherwise only
 * remove people. The backend scopes the answer to the team, so a manager who
 * does not run the team gets the same empty refusal a scoped read gives.
 */
export async function listMemberCandidates(
  team: number | string
): Promise<Employee[]> {
  const response = await fetch(`/api/hr/teams/${team}/member-candidates/`);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return (await response.json()) as Employee[];
}

export async function createTeam(input: TeamInput): Promise<Team> {
  return send<Team>("/api/hr/teams", "POST", input);
}

export async function updateTeam(
  id: number | string,
  input: Partial<TeamInput>
): Promise<Team> {
  return send<Team>(`/api/hr/teams/${id}`, "PATCH", input);
}

/**
 * Asks the backend whether the team can route applications, and what stands in
 * the way. The answer is a *list*, not a yes/no, because a chain with three
 * unstaffed steps should take HR one pass rather than three round trips.
 *
 * A team is in force from creation, so this is a standing check rather than a
 * gate before an activation: it is how HR finds the step that has lost its
 * approver since the chain was written.
 */
export async function validateTeam(id: number | string): Promise<TeamReadiness> {
  return send<TeamReadiness>(`/api/hr/teams/${id}/validate`, "POST");
}

/**
 * Retires a team. Stops it routing new applications; the applications already
 * inside it are untouched, because they are judged by the chain they were
 * submitted against.
 */
export async function deactivateTeam(id: number | string): Promise<Team> {
  return send<Team>(`/api/hr/teams/${id}/deactivate`, "POST");
}

/**
 * Point a team at one of the chains it already owns.
 *
 * This is the routing decision, not an edit to a chain: the chain keeps its
 * steps, and what changes is which of the team's chains new applications go
 * through. The backend refuses a chain the team does not own, so this can
 * never move a team onto somebody else's steps.
 */
export async function routeTeamThrough(
  teamId: number | string,
  workflowId: number | string | null
): Promise<Team> {
  return send<Team>(`/api/hr/teams/${teamId}/route`, "POST", {
    workflow: workflowId,
  });
}

export async function createCampus(input: CampusInput): Promise<Campus> {
  return send<Campus>("/api/hr/campuses", "POST", input);
}

/**
 * Edit a campus.
 *
 * The code is editable on purpose for as long as no team uses the campus: a
 * team stores the campus's id, not its code, so renaming the campus everywhere
 * is one write here rather than one per team.
 */
export async function updateCampus(
  id: number | string,
  input: Partial<CampusInput>
): Promise<Campus> {
  return send<Campus>(`/api/hr/campuses/${id}`, "PATCH", input);
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
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // A readiness response arrives on a failure too — that is the whole point
    // of asking before activating. Handing back an error that *is* the issue
    // list means a caller can render the reasons rather than a status code,
    // and the first problem is the message for a caller that only shows one.
    const issues = (data as { issues?: { message: string }[] } | null)?.issues;
    const headline = issues?.[0]?.message;
    throw Object.assign(new Error(headline ?? apiErrorMessage(data)), {
      readiness: issues ? (data as TeamReadiness) : undefined,
    });
  }
  return data;
}
