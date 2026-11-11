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
  /**
   * Why they are on that chain: a `"member"` is on its member list, a
   * `"step"` approves one of its steps. Neither can be added to another chain
   * until they are removed from where they are.
   */
  kind?: "member" | "step";
}

/**
 * The eligibility pool for one team's workflow memberships.
 *
 * `available` is whoever HR may add to the workflow without a refusal: active
 * team members not already placed on a different chain. `current` is who is on
 * the workflow already. `assigned_elsewhere` is people the team placed on
 * another chain — as a normal member or on one of its steps — and they show up
 * for context only: one person serves one chain of the team at a time, so they
 * become addable only after being removed from the chain they are on.
 */
export interface WorkflowMemberPool {
  team: { id: number; name: string; code: string };
  workflow: {
    id: number;
    name: string;
    state: string;
    is_active: boolean;
    is_routing: boolean;
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
  /** A wide approver may sit on several of a team's chains at once. */
  is_wide_approver?: boolean;
  added_by: number;
  created_at: string;
}