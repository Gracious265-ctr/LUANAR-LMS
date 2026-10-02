import { apiClientUrl } from "./api-client";

/**
 * Where a team is in its life. Three states, not a checkbox, because the step
 * between them is a decision: only an active team inside its effective window
 * routes an application, and a draft one is deliberately inert while HR is
 * still building it.
 *
 * Open-ended like the role codes: a status this build has not seen must survive
 * a round trip rather than crash a screen.
 */
export type TeamStatus = "draft" | "active" | "inactive";

export const TEAM_STATUS_CODES: TeamStatus[] = ["draft", "active", "inactive"];


/**
 * One problem standing between a team and being put into force. A code rather
 * than a message so a screen can decide *where* to point: an unstaffed step is
 * shown against its section, a date problem against the date field.
 */
export interface TeamReadinessIssue {
  code: string;
  field: string;
  message: string;
  section: number | null;
  approver_role: string | null;
}

/** The answer to "can this team be activated, and if not, why not?". */
export interface TeamReadiness {
  team: string;
  status: TeamStatus | string;
  ready: boolean;
  issues: TeamReadinessIssue[];
}

/**
 * One person on one section, for one period. A membership is a period rather
 * than a row that is either there or not, so "who could act on this date" is a
 * question the data can answer.
 */
export interface TeamSectionMember {
  id: number;
  user: number;
  user_name: string;
  user_email: string;
  effective_from: string;
  effective_to: string | null;
  is_effective: boolean;
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
  members: TeamSectionMember[];
}

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

export interface Team {
  id: number;
  name: string;
  code: string;
  description: string;
  /** Free text. Two active teams sharing one is a configuration problem, not an error. */
  department: string;
  campus: number | null;
  campus_name: string;
  /** The chain this team routes through, or null while the team is a draft. */
  workflow: number | null;
  workflow_name: string;
  status: TeamStatus | string;
  effective_from: string | null;
  effective_to: string | null;
  /** False outside the team's effective window, even when it is active. */
  is_effective: boolean;
  /** Required: a team with no chain routes nothing, so it cannot be saved without one. */
  stage_roles: TeamStageRole[];
  member_count: number;
  members: TeamMember[];
  /** The steps this team routes through, each with the people who can act. */
  sections: TeamSection[];
  created_at: string;
  updated_at: string;
}

/** One step as typed on a team's chain. */
export interface TeamSectionInput {
  name: string;
  approver_role: string;
  /** User ids staffed on the step. Only meaningful when creating the chain. */
  members?: number[];
}

/**
 * A team's approval chain, written inline.
 *
 * On create the chain is built with the team. On update it replaces the steps of
 * the chain the team already has — there is nowhere else a chain is created or
 * edited, because a chain is not a thing HR manages apart from the team it
 * belongs to.
 */
export interface TeamWorkflowInput {
  /** Optional on update; defaults to the chain's existing name. */
  name?: string;
  sections: TeamSectionInput[];
}

export interface TeamInput {
  name: string;
  description?: string;
  department?: string;
  campus?: number | null;
  effective_from?: string | null;
  effective_to?: string | null;
  /**
   * The team's approval chain. Omitted to leave the existing chain's steps
   * untouched; a team's chain can never be swapped for somebody else's.
   */
  new_workflow?: TeamWorkflowInput;
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

export interface TeamListOptions {
  /** Include retired teams. The default view is the teams that still matter. */
  includeInactive?: boolean;
  status?: TeamStatus | string;
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

export async function listTeams(options: TeamListOptions = {}): Promise<Team[]> {
  const params = new URLSearchParams();
  if (options.includeInactive) {
    params.set("include_inactive", "1");
  }
  if (options.status) {
    params.set("status", options.status);
  }
  const query = params.toString();
  return readAllPages<Team>(
    `/api/v1/teams/${query ? `?${query}` : ""}`
  );
}

export async function getTeam(id: number | string): Promise<Team> {
  return apiClientUrl<Team>(`/api/v1/teams/${id}/`);
}

export async function listCampuses(includeInactive = false): Promise<Campus[]> {
  const query = includeInactive ? "?include_inactive=1" : "";
  return readAllPages<Campus>(`/api/v1/campuses/${query}`);
}

// The status label map and the two helpers over it live in `teams-client.ts`:
// they are pure, and the team table is rendered inside a client section, which
// would otherwise drag `api-client`'s `next/headers` into the browser bundle.
// Re-exported here so the server pages and components keep importing from the
// module they already use.
export {
  TEAM_STATUS_LABELS,
  teamStatusLabel,
  teamStatusBadgeClass,
} from "./teams-client";
