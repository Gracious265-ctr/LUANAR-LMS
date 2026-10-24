import { describe, expect, it } from "vitest";

import {
  canAccessTeams,
  isTeamsAdministrator,
} from "@/lib/nav/teams-nav";

/**
 * The one predicate the module's pages share.
 *
 * HR and superusers administer every team; a designated manager reaches their
 * own. These are what the page guards call, so they are tested directly rather
 * than only through a rendered page.
 */
describe("workflows access", () => {
  it("treats HR and superusers as administrators", () => {
    expect(isTeamsAdministrator({ role: "hr" })).toBe(true);
    expect(isTeamsAdministrator({ role: "employee", is_superuser: true })).toBe(
      true
    );
    expect(canAccessTeams({ role: "hr" })).toBe(true);
    expect(
      canAccessTeams({ role: "employee", is_superuser: true })
    ).toBe(true);
  });

  it("admits a designated team manager without administrator rights", () => {
    const manager = { role: "employee", manages_teams: true };
    expect(canAccessTeams(manager)).toBe(true);
    expect(isTeamsAdministrator(manager)).toBe(false);
  });

  it("refuses an ordinary employee, a missing user, and null", () => {
    for (const viewer of [
      { role: "employee" },
      { role: "employee", manages_teams: false },
      null,
      undefined,
    ]) {
      expect(canAccessTeams(viewer)).toBe(false);
      expect(isTeamsAdministrator(viewer)).toBe(false);
    }
  });
});
