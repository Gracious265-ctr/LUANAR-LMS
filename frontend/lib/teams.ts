import { apiClientUrl } from "./api-client";

/**
 * One person on one section of a team's workflow. A person may sit on several
 * sections, so the list of sections they belong to travels with them.
 */
export interface TeamMember {
  user: number;
  user_name: string;
  user_email: string;
  sections: { id: number; name: string; order: number }[];
  roles: { id: number; code: string; label: string }[];
}

export interface TeamStageRole {
  id: number;
  code: string;
  label: string;
}

/** A team row's read-only summary of one step of the workflow it routes through. */
export interface TeamSection {
  id: number;
  name: string;
  order: number;
  is_active: boolean;
  approver_role: string;
  approver_role_label: string;
  member_count: number;
}

export interface Team {
  id: number;
  name: string;
  code: string;
  description: string;
  campus: number | null;
  campus_name: string;
  /** Required: a team with no workflow routes nothing, so it cannot be saved without one. */
  workflow: number;
  workflow_name: string;
  is_active: boolean;
  /** The roles this team's workflow asks for — the member role picker's options. */
  stage_roles: TeamStageRole[];
  member_count: number;
  members: TeamMember[];
  /** The steps this team routes through, with how many people can act at each. */
  sections: TeamSection[];
  created_at: string;
  updated_at: string;
}

export interface TeamInput {
  name: string;
  description?: string;
  campus?: number | null;
  workflow: number;
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
