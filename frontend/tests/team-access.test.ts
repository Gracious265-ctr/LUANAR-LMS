import { describe, expect, it } from "vitest";

import {
  canConfigureChains,
  canRouteTeam,
  visibleTeamTabs,
} from "@/lib/team-access";

/**
 * The team screens follow the handover the API enforces: HR creates a team and
 * names its manager, the manager runs the team's roster, steps, and chains, and
 * HR keeps the team's identity, wide-role holdings, and which chain routes.
 * These predicates are what stop a screen offering an action the server would
 * refuse, so pin them here.
 */
describe("team access by role", () => {
  describe("visible tabs", () => {
    it("gives HR the overview and the team-wide approvers", () => {
      expect(visibleTeamTabs(true)).toEqual(["overview", "approvers"]);
    });

    it("gives a manager the overview, steps, and members", () => {
      expect(visibleTeamTabs(false)).toEqual([
        "overview",
        "steps",
        "members",
      ]);
    });

    it("never shows a manager the approvers tab", () => {
      expect(visibleTeamTabs(false)).not.toContain("approvers");
    });

    it("never shows HR the step-staffing or roster tabs", () => {
      expect(visibleTeamTabs(true)).not.toContain("steps");
      expect(visibleTeamTabs(true)).not.toContain("members");
    });
  });

  describe("chain configuration", () => {
    it("belongs to the manager, not HR", () => {
      expect(canConfigureChains(false)).toBe(true);
      expect(canConfigureChains(true)).toBe(false);
    });
  });

  describe("routing", () => {
    it("belongs to the manager, not HR", () => {
      expect(canRouteTeam(false)).toBe(true);
      expect(canRouteTeam(true)).toBe(false);
    });
  });
});
