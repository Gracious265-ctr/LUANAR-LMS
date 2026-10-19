import { describe, expect, it } from "vitest";

import {
  canAccessOrganisation,
  isOrganisationAdministrator,
} from "@/lib/nav/organisation-nav";

/**
 * The one predicate the module's pages share.
 *
 * HR and superusers administer every team; a designated manager reaches their
 * own. These are what the page guards call, so they are tested directly rather
 * than only through a rendered page.
 */
describe("workflows access", () => {
  it("treats HR and superusers as administrators", () => {
    expect(isOrganisationAdministrator({ role: "hr" })).toBe(true);
    expect(isOrganisationAdministrator({ role: "employee", is_superuser: true })).toBe(
      true
    );
    expect(canAccessOrganisation({ role: "hr" })).toBe(true);
    expect(
      canAccessOrganisation({ role: "employee", is_superuser: true })
    ).toBe(true);
  });

  it("admits a designated team manager without administrator rights", () => {
    const manager = { role: "employee", manages_teams: true };
    expect(canAccessOrganisation(manager)).toBe(true);
    expect(isOrganisationAdministrator(manager)).toBe(false);
  });

  it("refuses an ordinary employee, a missing user, and null", () => {
    for (const viewer of [
      { role: "employee" },
      { role: "employee", manages_teams: false },
      null,
      undefined,
    ]) {
      expect(canAccessOrganisation(viewer)).toBe(false);
      expect(isOrganisationAdministrator(viewer)).toBe(false);
    }
  });
});
