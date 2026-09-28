import type { Campus, CampusInput, Team, TeamInput, TeamMember } from "./teams";
import { apiErrorMessage } from "./utils";

export async function createTeam(input: TeamInput): Promise<Team> {
  return send<Team>("/api/hr/teams", "POST", input);
}

export async function updateTeam(
  id: number | string,
  input: Partial<TeamInput>
): Promise<Team> {
  return send<Team>(`/api/hr/teams/${id}`, "PATCH", input);
}

export async function createCampus(input: CampusInput): Promise<Campus> {
  return send<Campus>("/api/hr/campuses", "POST", input);
}

export async function addTeamMember(input: {
  team: number | string;
  user: number | string;
  role: string;
}): Promise<TeamMember> {
  return send<TeamMember>("/api/hr/team-members", "POST", input);
}

export async function removeTeamMember(id: number | string): Promise<void> {
  await send<void>(`/api/hr/team-members/${id}`, "DELETE");
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
