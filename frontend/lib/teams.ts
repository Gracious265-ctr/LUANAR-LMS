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

export const TEAM_STATUS_LABELS: Record<TeamStatus, string> = {
  draft: "Draft",
  active: "Active",
  inactive: "Retired",
};

export const TEAM_STATUS_CODES: TeamStatus[] = ["draft", "active", "inactive"];

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
 * The one person a step routes to.
 *
 * A step has exactly one approver, so the read shape says so: one person, or
 * `null` for a step nobody has been appointed to yet. A roster would read as
 * "whichever of these acts first", which is the configuration the stage model
 * forbids.
 */
export interface TeamSectionApprover {
  id: number;
  user_name: string;
  user_email: string;
}

/** A team row's read-only summary of one step of the workflow it routes through. */
export interface TeamSection {
  id: number;
  name: string;
  order: number;
  is_active: boolean;
  approver_role: string;
  approver_role_label: string;
  approver: TeamSectionApprover | null;
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
  /** A pick from the departments HR maintains; it decides who may be appointed. */
  department: number | null;
  department_name: string;
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
  /**
   * The one person appointed to the step, by user id. Omitted to leave an
   * existing step's approver alone, which is how an edit that only renames a
   * step does not unappoint the person on it.
   */
  approver?: number | null;
}

/** One person the backend says may be appointed to a step of a team's chain. */
export interface EligibleApprover {
  id: number;
  full_name: string;
  email: string;
  designation: string;
}

/**
 * The people eligible for one team's steps, and which department they were
 * scoped to.
 *
 * Returned rather than filtered in the browser: eligibility is the department,
 * so the list must come from the same rule the write enforces, or the picker
 * would offer people the backend then refuses.
 */
export interface EligibleApprovers {
  department: { id: number; name: string };
  candidates: EligibleApprover[];
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
  /** The department this team belongs to, as a pick from the departments list. */
  department?: number | null;
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
