/**
 * Team membership shapes: the roster, and the workflow-member eligibility pool.
 *
 * Normal membership of a chain is not stored on the workflow's steps — a step
 * is a slice of the chain, not the chain — and not on the employee either.
 * It is its own assignment, so its shape here is its own too: the roster
 * answers "who is on this team and what are they on", the pool answers "who
 * *may* be put on this workflow without the backend refusing them".
 */

/** The workflow footprint of one team member, as the roster reads it. */
export interface TeamMemberWorkflowRef {
  workflow_id: number;
  workflow_name: string;
}

/** One employee on a team, with their workflow footprint. */
export interface TeamMemberSummary {
  id: number;
  user: number;
  full_name: string;
  email: string;
  designation: string;
  category: string;
  faculty: string;
  grade: string;
  is_active: boolean;
  /** True when this person staffs a step of one of this team's chains. */
  is_section_approver: boolean;
  /** The team-wide role they hold on this team, or null. */
  team_role: string | null;
  workflow_memberships: TeamMemberWorkflowRef[];
  workflow_count: number;
}

/** One employee the roster's add picker may offer, as the backend scopes it. */
export interface TeamMemberCandidate {
  /** The user id the add writes. */
  id: number;
  full_name: string;
  email: string;
  designation: string;
}

/** One candidate for a workflow's normal-member pool. */
export interface PoolPerson {
  id: number;
  user: number;
  full_name: string;
  email: string;
  designation: string;
  category: string;
  faculty: string;
  grade: string;
  is_active: boolean;
}

/** A pool row for somebody already on another of the team's chains. */
export interface AssignedElsewherePerson extends PoolPerson {
  workflow_id: number;
  workflow_name: string;
}

/**
 * The eligibility pool for one team's workflow memberships.
 *
 * `available` is whoever HR may add to the workflow without a refusal: active
 * team members not already a normal member of a different chain. `current` is
 * who is on the workflow already, and `assigned_elsewhere` is read-only — the
 * people the team placed on other chains, named so the UI can say *where*.
 */
export interface WorkflowMemberPool {
  team: { id: number; name: string; code: string };
  workflow: {
    id: number;
    name: string;
    state: string;
    is_active: boolean;
  } | null;
  available: PoolPerson[];
  current: PoolPerson[];
  assigned_elsewhere: AssignedElsewherePerson[];
}

/** One normal member of a workflow, as read back from the workflow detail. */
export interface WorkflowMember {
  id: number;
  workflow: number;
  workflow_name: string;
  user: number;
  user_name: string;
  user_email: string;
  designation: string;
  team: number;
  team_name: string;
  added_by: number;
  created_at: string;
}

/**
 * A normal member as the *workflow* payload embeds it.
 *
 * Lighter than :class:`WorkflowMember`: the workflow detail carries each member
 * as the person and the team, without the membership row's own id, the
 * ``added_by`` audit, or the flattened ``user_name``/``designation`` fields the
 * dedicated members endpoint builds. The two are kept apart so a screen cannot
 * read a field the embedded shape never sends.
 */
export interface WorkflowMemberRef {
  id: number;
  user: number;
  full_name: string;
  email: string;
  team: number;
  created_at: string;
}