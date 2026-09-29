/**
 * Read shapes for a team's approval chain.
 *
 * A workflow is not a thing HR manages on its own any more: it comes into being
 * with the team it belongs to, and it is read through that team. What survives
 * here is the shape — a chain's steps and the people who can act at each — which
 * the team screens and the membership editor both need. There is no client for
 * it on purpose: nothing writes a chain except creating or updating a team.
 */

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
  description: string;
  is_active: boolean;
  members: SectionMember[];
  member_count: number;
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
