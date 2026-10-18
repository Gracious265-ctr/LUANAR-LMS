import { apiClientUrl } from "./api-client";
import type { WorkflowMemberRef } from "./team-members";

/**
 * A chain's shape, and how it is read and written.
 *
 * A team may own several chains, so a chain is read on its own — the team's
 * workflow screen needs its steps, how each one resolves its approver, and who
 * is a member of each. It is also written on its own now, for the same reason:
 * HR builds the replacement chain alongside the live one rather than swapping
 * the live chain's steps out from under the applications already inside it.
 * What never changes is that the chain belongs to the team it was created for.
 */

/**
 * Where a step's approver comes from, as the backend resolved it.
 *
 * The read contract is the answer the resolver already gave — ``source`` is
 * who provides the person (the step itself, or a team-, campus- or
 * institution-wide holding), ``label`` is that in words, and ``user_name`` is
 * the person, when there is one. A screen shows this without re-deriving the
 * rule.
 */
export interface WorkflowSectionResolution {
  source: "section" | "team" | "campus" | "institution" | "unresolved";
  automatic: boolean;
  user: number | null;
  user_name: string | null;
  label: string;
}

/**
 * One step of a chain. `members` are the people who may act for it: the step is
 * decided by whichever of them acts first, so a step is not a single approver
 * but a roster with one seat taken per decision.
 */
export interface WorkflowSection {
  id: number;
  name: string;
  order: number;
  /** The role's stable code. Open-ended: HR can add roles this build never saw. */
  approver_role: string;
  /** The role's label as read, so a chain is readable without a second lookup. */
  approver_role_label: string;
  /**
   * The one person staffed on this step by HR, when there is one. A step has
   * exactly one approver, so the edit form can prefill its picker with this
   * rather than guessing from the resolution.
   */
  approver: number | null;
  /** The approver's name, echoed for display. */
  approver_name: string | null;
  /**
   * Who the backend would route this step to, and where that person comes
   * from. Display data rather than an instruction: it is the answer the
   * resolver already gave, so a screen can show the fallback chain without
   * being a second place the rule is written.
   */
  resolution: WorkflowSectionResolution;
  description: string;
  is_active: boolean;
  members: SectionMember[];
  member_count: number;
  /** The people who held this step, and when. */
  memberships: SectionMember[];
}

/**
 * One person on one step, for one period. A membership is a period rather than
 * a row that is either there or not, so the question "could this person act on
 * the third of March" has an answer that survives a handover.
 */
export interface SectionMember {
  id: number;
  section: number;
  section_name: string;
  section_order: number;
  workflow: number;
  approver_role: string;
  approver_role_label: string;
  user: number;
  user_name: string;
  user_email: string;
  effective_from: string;
  effective_to: string | null;
  /** True when the period covers today — the default view's answer. */
  is_effective: boolean;
  created_at: string;
}

/**
 * The lifecycle a chain is in, as the backend reports it.
 *
 * A chain has no activation of its own: it is in force exactly when the team
 * that routes through it is, so `is_active` is a stored flag that only becomes
 * meaningful next to the team's status. The label exists so a screen can say
 * "live"/"not in force" without re-deriving the rule.
 */
export type WorkflowState = "routing" | "standby" | "draft";

export const WORKFLOW_STATE_LABELS: Record<WorkflowState, string> = {
  routing: "In force",
  standby: "Owned, not routing",
  draft: "Not yet owned by a team",
};

export function workflowStateLabel(state: string): string {
  return WORKFLOW_STATE_LABELS[state as WorkflowState] ?? state;
}

/**
 * One approval step as it is written, not as it is read.
 *
 * The role is a code, the same open-ended vocabulary the rest of the chain
 * vocabulary uses, and the person is optional: leaving it out keeps whoever is
 * already appointed, which is how renaming a step does not unappoint the person
 * on it.
 */
export interface WorkflowSectionInput {
  name?: string;
  approver_role: string;
  order?: number;
  approver?: number | null;
}

/**
 * A chain, as configured.
 *
 * `team` is the team that *owns* it — the team it was built for, which is the
 * team that may edit it. `is_routing` says whether that team currently routes
 * through it, which is a separate question: a team may own several chains and
 * route exactly one.
 */
export interface Workflow {
  id: number;
  name: string;
  team: number | null;
  team_name: string;
  effective_from: string | null;
  /** The end of the academic calendar this chain was written against, if any. */
  effective_to: string | null;
  is_active: boolean;
  state: WorkflowState | string;
  is_routing: boolean;
  section_count: number;
  sections: WorkflowSection[];
  /** The normal members of this chain (team members, not step approvers). */
  members: WorkflowMemberRef[];
}

export interface WorkflowInput {
  /** Required: a chain carries its own name, not the team's. */
  name?: string;
  /** Required on create, and on edit it must name a chain this team already owns. */
  team?: number | null;
  /**
   * The whole ordered step list. Sent as a replacement, not a merge: the chain
   * is described end to end so there is no half-edited sequence left behind.
   */
  sections?: WorkflowSectionInput[];
  /**
   * The chain's normal members, as user ids of the owning team's employees.
   *
   * Sent as a replacement, not a merge. Absent means "leave membership alone",
   * which is how editing just the steps does not clear the roster; an empty
   * list means "no members".
   */
  members?: number[];
}

interface Paginated<T> {
  count: number;
  next: string | null;
  results: T[];
}

/** Whole list of one team's chains — a picker must not see one page of them. */
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

export async function listWorkflows(
  options: { team?: number | string; routing?: boolean } = {}
): Promise<Workflow[]> {
  const params = new URLSearchParams();
  if (options.team !== undefined) {
    params.set("team", String(options.team));
  }
  if (options.routing !== undefined) {
    params.set("routing", options.routing ? "1" : "0");
  }
  const query = params.toString();
  return readAllPages<Workflow>(`/api/v1/workflows/${query ? `?${query}` : ""}`);
}

export async function getWorkflow(id: number | string): Promise<Workflow> {
  return apiClientUrl<Workflow>(`/api/v1/workflows/${id}/`);
}
