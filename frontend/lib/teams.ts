import { apiClientUrl } from "./api-client";

export interface TeamMember {
  id: number;
  team: number;
  user: number;
  user_name: string;
  role: string;
  role_label: string;
  created_at: string;
}

export interface TeamStageRole {
  id: number;
  code: string;
  label: string;
}

export interface Team {
  id: number;
  name: string;
  code: string;
  description: string;
  campus: number | null;
  campus_name: string;
  workflow: number | null;
  workflow_name: string;
  is_active: boolean;
  /** The roles this team's workflow asks for — the member role picker's options. */
  stage_roles: TeamStageRole[];
  member_count: number;
  members: TeamMember[];
  created_at: string;
  updated_at: string;
}

export interface TeamInput {
  name: string;
  description?: string;
  campus?: number | null;
  workflow?: number | null;
  is_active?: boolean;
}

export interface Campus {
  id: number;
  name: string;
  code: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CampusInput {
  name: string;
  code: string;
  description?: string;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  results: T[];
}

/** Whole list, not page one: a picker built from one page understates the choice. */
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

export async function listTeams(includeInactive = false): Promise<Team[]> {
  const query = includeInactive ? "?include_inactive=1" : "";
  return readAllPages<Team>(`/api/v1/teams/${query}`);
}

export async function getTeam(id: number | string): Promise<Team> {
  return apiClientUrl<Team>(`/api/v1/teams/${id}/`);
}

export async function listCampuses(includeInactive = false): Promise<Campus[]> {
  const query = includeInactive ? "?include_inactive=1" : "";
  return readAllPages<Campus>(`/api/v1/campuses/${query}`);
}
