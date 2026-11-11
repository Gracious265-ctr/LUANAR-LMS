import type { Team, WorkflowRef } from "./teams";
import type { WorkflowSection } from "./workflows";

/**
 * Reading a team's chains as a list of steps.
 *
 * A team may own several chains — the one it routes through by default, plus any
 * built beside it — and "who decides at each step" is a question with an answer
 * for every one of them. Two different endpoints describe those steps:
 *
 * - `Team.sections` carries the steps of the chain the team *routes* through,
 *   already resolved to the person who acts and summarised for a team screen.
 * - `WorkflowSection`, from reading a chain on its own, describes any chain.
 *
 * Both reduce to `ChainStep`, so one listing can render either without caring
 * where the row came from. This module holds only that reduction and the ordering
 * that goes with it — no fetching — so it is safe on either side of the wire and
 * can be tested without a server.
 */

/**
 * One step as a chain listing shows it, whichever chain it came from.
 *
 * `approver.user_email` is optional because the chain-scoped read returns a name
 * without an address; nothing displays the address, so an absent one is fine.
 */
export interface ChainStep {
  id: number;
  name: string;
  order: number;
  approver_role: string;
  approver_role_label: string;
  approver: { id: number; user_name: string; user_email?: string } | null;
}

/** One chain and its steps, as a "who decides at each step" listing needs them. */
export interface TeamChainSteps {
  chain: WorkflowRef;
  /** Null when the chain could not be read; the listing says so in place. */
  steps: ChainStep[] | null;
}

/**
 * Every chain a team owns, the default one first.
 *
 * `workflows` is the list endpoint's answer, which the team page catches to an
 * empty list on failure. In that case this falls back to the chain the team
 * routes through, so one failed listing cannot make a team that does have a
 * chain look like it owns none. The rest are ordered by name, because the order
 * the list endpoint happens to return is not a meaning.
 */
export function teamChains(team: Team, workflows: WorkflowRef[]): WorkflowRef[] {
  const chains: WorkflowRef[] =
    workflows.length > 0
      ? workflows
      : team.workflow !== null
        ? [
            {
              id: team.workflow,
              name: team.workflow_name || "Default chain",
              is_routing: true,
              section_count: team.sections.length,
              effective_from: team.effective_from,
              is_active: team.status === "active",
            },
          ]
        : [];
  return [...chains].sort(
    (a, b) =>
      Number(b.is_routing) - Number(a.is_routing) || a.name.localeCompare(b.name)
  );
}

/**
 * Pair each chain with its steps.
 *
 * The team payload already carries the steps of the chain it routes through, so
 * those are not read again; `details` holds the chains read on their own. A chain
 * missing from `details`, or mapped to null there, is one that could not be read,
 * and it keeps its place in the list so a failure is visible rather than silent.
 */
export function assembleChainSteps(
  chains: WorkflowRef[],
  team: Team,
  details: Record<number, WorkflowSection[] | null>
): TeamChainSteps[] {
  return chains.map((chain) => {
    if (chain.id === team.workflow) {
      return { chain, steps: team.sections };
    }
    const sections = details[chain.id];
    if (!sections) {
      return { chain, steps: null };
    }
    return {
      chain,
      steps: sections.map((section) => ({
        id: section.id,
        name: section.name,
        order: section.order,
        approver_role: section.approver_role,
        approver_role_label: section.approver_role_label,
        approver:
          section.approver === null
            ? null
            : { id: section.approver, user_name: section.approver_name ?? "" },
      })),
    };
  });
}
