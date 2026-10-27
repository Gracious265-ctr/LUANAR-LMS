import { apiClientUrl } from "./api-client";
import type { TeamCategory } from "./team-category";

// The category vocabulary is client-safe and lives beside this module, not
// inside it: this file reads Django through `api-client`, which is server-only,
// and a client component that imported the labels from here would put
// `next/headers` into the browser bundle. Re-exported so server callers keep
// one import path.
export {
  TEAM_CATEGORY_CODES,
  TEAM_CATEGORY_LABELS,
  teamCategoryBadgeTone,
  teamCategoryLabel,
  type TeamCategory,
} from "./team-category";

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

/** The answer to "can this team route, and if not, why not?". */
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

/**
 * How a step finds the person who acts for it.
 *
 * Display data rather than an instruction: it is what the backend already
 * resolved, so a screen can say "staffed on this team" or "falls back to a
 * campus-wide holder" without being the second place the rule is written.
 */
export type SectionResolution = "staffed" | "team_wide" | "campus_wide" | "institution_wide" | "unresolved";

export const SECTION_RESOLUTION_LABELS: Record<SectionResolution, string> = {
  staffed: "Appointed on this team",
  team_wide: "Team-wide holder",
  campus_wide: "Campus-wide holder",
  institution_wide: "Institution-wide holder",
  unresolved: "Nobody can act here yet",
};

export function sectionResolutionLabel(resolution: string): string {
  return SECTION_RESOLUTION_LABELS[resolution as SectionResolution] ?? resolution;
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
  /** Who the backend would route this step to, and where that person comes from. */
  resolution: string;
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

/**
 * A chain the team owns, named so a screen can show every one of them without
 * reading them all. `is_routing` is the team's default chain — a team routes
 * every chain its people are enrolled on, and the default is where the
 * unenrolled (and a wide approver holding several) route. Changing it is a
 * decision rather than an edit to whichever chain happens to be first.
 */
export interface WorkflowRef {
  id: number;
  name: string;
  is_routing: boolean;
  section_count: number;
  effective_from: string | null;
  is_active: boolean;
}

export interface Team {
  id: number;
  name: string;
  code: string;
  description: string;
  /** Academic teams sit at a campus; administration teams do not. */
  category: TeamCategory | string;
  /** The campus this team sits in, required when the category is academic. */
  campus: number | null;
  campus_name: string;
  /** The chain this team routes through, or null while the team is a draft. */
  workflow: number | null;
  workflow_name: string;
  /** Every chain this team owns, including the one it routes through. */
  workflows: WorkflowRef[];
  status: TeamStatus | string;
  effective_from: string | null;
  effective_to: string | null;
  /** False outside the team's effective window, even when it is active. */
  is_effective: boolean;
  /**
   * Whether the signed-in user is this team's designated manager. The roster
   * and the default chain are the manager's to change, so HR reads the same
   * team read-only; the server refuses those writes to anyone else.
   */
  is_team_manager: boolean;
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
 * The people eligible for one team's steps, and which team they were scoped to.
 *
 * Returned rather than filtered in the browser: eligibility is the team, so the
 * list must come from the same rule the write enforces, or the picker would
 * offer people the backend then refuses.
 */
export interface EligibleApprovers {
  team: { id: number; name: string };
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
  /** Academic teams must name a campus; administration teams must not. */
  category?: TeamCategory;
  /** The campus this team sits in. Required when the category is academic. */
  campus?: number | null;
  effective_from?: string | null;
  effective_to?: string | null;
  /**
   * The chain this team routes through. On create it must be omitted — a new
   * team cannot adopt a chain that already exists, because that chain belongs
   * to whichever team it was built for. On edit it must name one the team
   * already owns, which is how HR points a team at its replacement chain.
   */
  workflow?: number | null;
  /**
   * The team's approval chain. Omitted to leave the existing chain's steps
   * untouched; a team's chain can never be swapped for somebody else's.
   */
  new_workflow?: TeamWorkflowInput;
  /**
   * The manager designated at creation: the team-scoped role they hold, and the
   * category-matching employee who holds it. Written on create only — a team's
   * manager is changed from the team's Approvers tab afterwards, where the
   * wide-holder panel offers "Make manager".
   */
  manager?: { role: number; user: number };
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
  /** Only teams of this kind. Used by the campus and approver screens. */
  category?: TeamCategory;
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
  if (options.category) {
    params.set("category", options.category);
  }
  const query = params.toString();
  return readAllPages<Team>(
    `/api/v1/teams/${query ? `?${query}` : ""}`
  );
}

/**
 * One team's workflows, and which one it routes through.
 *
 * Scoped by team rather than read whole: a team may own several chains, and
 * the question this answers is always "which chains does *this* team have".
 */
export async function listTeamWorkflows(
  team: number | string
): Promise<WorkflowRef[]> {
  return readAllPages<WorkflowRef>(`/api/v1/workflows/?team=${team}`);
}

export async function getTeam(id: number | string): Promise<Team> {
  return apiClientUrl<Team>(`/api/v1/teams/${id}/`);
}

export async function listCampuses(includeInactive = false): Promise<Campus[]> {
  const query = includeInactive ? "?include_inactive=1" : "";
  return readAllPages<Campus>(`/api/v1/campuses/${query}`);
}

export async function getCampus(id: number | string): Promise<Campus> {
  return apiClientUrl<Campus>(`/api/v1/campuses/${id}/`);
}

// The status label map and the two helpers over it live in `teams-client.ts`:
// they are pure, and the team table is rendered inside a client section, which
// would otherwise drag `api-client`'s `next/headers` into the browser bundle.
// Re-exported here so the server pages and components keep importing from the
// module they already use.
export {
  TEAM_STATUS_LABELS,
  teamStatusLabel,
  teamStatusBadgeTone,
} from "./teams-client";
