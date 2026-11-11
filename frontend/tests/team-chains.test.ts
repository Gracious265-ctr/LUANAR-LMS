import { describe, expect, it } from "vitest";

import {
  assembleChainSteps,
  teamChains,
  type ChainStep,
} from "@/lib/team-chains";
import type { Team, WorkflowRef } from "@/lib/teams";
import type { WorkflowSection } from "@/lib/workflows";

/**
 * A team can own more than one chain. The "who decides at each step" screen used
 * to read `Team.sections`, which carries the steps of the chain the team *routes*
 * through and nothing else — so a second chain was invisible, and a team whose
 * routed chain had no steps looked like it had none at all.
 *
 * These cover the two pieces that decide what that screen lists: which chains
 * appear and in what order, and how each chain's steps are read out of whichever
 * endpoint described them.
 */

const DEFAULT_CHAIN: WorkflowRef = {
  id: 1,
  name: "Academic approval",
  is_routing: true,
  section_count: 2,
  effective_from: "2026-01-01",
  is_active: true,
};

const SECOND_CHAIN: WorkflowRef = {
  id: 2,
  name: "Replacement chain",
  is_routing: false,
  section_count: 1,
  effective_from: null,
  is_active: true,
};

function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 4,
    name: "Bunda College Faculty",
    code: "bunda-faculty",
    description: "",
    category: "academic",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    workflows: [],
    status: "active",
    effective_from: "2026-01-01",
    effective_to: null,
    is_effective: true,
    is_team_manager: true,
    manager_user: 7,
    manager_name: "Hana Reyes",
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "lead", label: "Team Leader" },
    ],
    member_count: 1,
    roster_count: 0,
    members: [],
    sections: [
      {
        id: 11,
        name: "Direct supervisor",
        order: 1,
        is_active: true,
        approver_role: "supervisor",
        approver_role_label: "Supervisor",
        approver: {
          id: 3,
          user_name: "Jane Dean",
          user_email: "jane.dean@luanar.ac.mw",
        },
        resolution: "staffed",
      },
    ],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function workflowSection(
  overrides: Partial<WorkflowSection> = {}
): WorkflowSection {
  return {
    id: 41,
    name: "Registrar review",
    order: 1,
    approver_role: "lead",
    approver_role_label: "Team Leader",
    approver: 5,
    approver_name: "Bob Lead",
    resolution: {
      source: "section",
      automatic: false,
      user: 5,
      user_name: "Bob Lead",
      label: "Appointed on this chain",
    },
    description: "",
    is_active: true,
    members: [],
    member_count: 1,
    memberships: [],
    ...overrides,
  };
}

describe("teamChains", () => {
  it("lists every chain the team owns, default first", () => {
    // Deliberately not in the order the list endpoint returned them: the default
    // chain is the one an unenrolled person routes through, so it leads.
    const chains = teamChains(makeTeam(), [SECOND_CHAIN, DEFAULT_CHAIN]);

    expect(chains.map((chain) => chain.name)).toEqual([
      "Academic approval",
      "Replacement chain",
    ]);
    expect(chains[0].is_routing).toBe(true);
  });

  it("orders the non-default chains by name", () => {
    const chains = teamChains(makeTeam(), [
      { ...SECOND_CHAIN, id: 2, name: "Zonal chain" },
      { ...SECOND_CHAIN, id: 3, name: "Administrative chain" },
      DEFAULT_CHAIN,
    ]);

    expect(chains.map((chain) => chain.name)).toEqual([
      "Academic approval",
      "Administrative chain",
      "Zonal chain",
    ]);
  });

  it("falls back to the routed chain when the chain list could not be read", () => {
    // The page catches a failed listing to []. Showing "this team owns no chains
    // yet" there would be a lie about a team that is routing right now.
    const chains = teamChains(makeTeam({ sections: [] }), []);

    expect(chains).toHaveLength(1);
    expect(chains[0]).toMatchObject({
      id: 1,
      name: "Academic approval",
      is_routing: true,
      section_count: 0,
    });
  });

  it("lists nothing when the team has no chains at all", () => {
    expect(teamChains(makeTeam({ workflow: null }), [])).toEqual([]);
  });
});

describe("assembleChainSteps", () => {
  it("reads the routed chain's steps from the team, and others from their own read", () => {
    const team = makeTeam();
    const chains = teamChains(team, [DEFAULT_CHAIN, SECOND_CHAIN]);

    const result = assembleChainSteps(chains, team, {
      [SECOND_CHAIN.id]: [workflowSection()],
    });

    expect(result).toHaveLength(2);

    const [routed, other] = result;
    // The routed chain's steps come straight from the team payload.
    expect(routed.chain.id).toBe(DEFAULT_CHAIN.id);
    expect(routed.steps?.map((step: ChainStep) => step.name)).toEqual([
      "Direct supervisor",
    ]);
    expect(routed.steps?.[0].approver?.user_name).toBe("Jane Dean");

    // The second chain's steps are reduced from the chain-scoped read.
    expect(other.chain.id).toBe(SECOND_CHAIN.id);
    expect(other.steps).toEqual([
      {
        id: 41,
        name: "Registrar review",
        order: 1,
        approver_role: "lead",
        approver_role_label: "Team Leader",
        approver: { id: 5, user_name: "Bob Lead" },
      },
    ]);
  });

  it("carries an unstaffed step as having no approver, not as a missing step", () => {
    const team = makeTeam();
    const chains = teamChains(team, [DEFAULT_CHAIN, SECOND_CHAIN]);

    const [, other] = assembleChainSteps(chains, team, {
      [SECOND_CHAIN.id]: [
        workflowSection({ approver: null, approver_name: null }),
      ],
    });

    expect(other.steps).toHaveLength(1);
    expect(other.steps?.[0].approver).toBeNull();
  });

  it("keeps a chain it could not read in the list, marked unreadable", () => {
    // Dropping it would make the screen quietly claim the team owns fewer chains
    // than it does; the listing says so in place instead.
    const team = makeTeam();
    const chains = teamChains(team, [DEFAULT_CHAIN, SECOND_CHAIN]);

    const result = assembleChainSteps(chains, team, {
      [SECOND_CHAIN.id]: null,
    });

    expect(result.map((entry) => entry.chain.id)).toEqual([
      DEFAULT_CHAIN.id,
      SECOND_CHAIN.id,
    ]);
    expect(result[1].steps).toBeNull();
  });

  it("marks a chain missing from the details as unreadable rather than empty", () => {
    const team = makeTeam();
    const chains = teamChains(team, [DEFAULT_CHAIN, SECOND_CHAIN]);

    const [, other] = assembleChainSteps(chains, team, {});

    // Null, not [] — an empty list would render as "this chain has no steps yet".
    expect(other.steps).toBeNull();
  });
});
