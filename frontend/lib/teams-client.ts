import type {
  Campus,
  CampusInput,
  Team,
  TeamInput,
  TeamReadiness,
  TeamStatus,
} from "./teams";
import { apiErrorMessage } from "./utils";

export const TEAM_STATUS_LABELS: Record<TeamStatus, string> = {
  draft: "Draft",
  active: "Active",
  inactive: "Retired",
};

export function teamStatusLabel(status: string): string {
  return TEAM_STATUS_LABELS[status as TeamStatus] ?? status;
}

export function teamStatusBadgeClass(status: string): string {
  switch (status) {
    case "active":
      return "bg-brand-secondary-subtle text-brand-secondary";
    case "inactive":
      return "bg-surface-muted text-text-muted";
    default:
      return "bg-status-pending-subtle text-status-pending";
  }
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
 * Asks the backend whether the team could be put into force, and what stands in
 * the way. The answer is a *list*, not a yes/no, because a chain with three
 * unstaffed steps should take HR one pass rather than three round trips.
 */
export async function validateTeam(id: number | string): Promise<TeamReadiness> {
  return send<TeamReadiness>(`/api/hr/teams/${id}/validate`, "POST");
}

/**
 * Puts a team into force. Refused, with the same issue list, if the team is not
 * ready — so the caller has one place to read a refusal from and no way to
 * force a broken chain on.
 */
export async function activateTeam(id: number | string): Promise<Team> {
  return send<Team>(`/api/hr/teams/${id}/activate`, "POST");
}

/**
 * Retires a team. Stops it routing new applications; the applications already
 * inside it are untouched, because they are judged by the chain they were
 * submitted against.
 */
export async function deactivateTeam(id: number | string): Promise<Team> {
  return send<Team>(`/api/hr/teams/${id}/deactivate`, "POST");
}

export async function createCampus(input: CampusInput): Promise<Campus> {
  return send<Campus>("/api/hr/campuses", "POST", input);
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
