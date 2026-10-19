import { describe, expect, it } from "vitest";

import {
  DOCUMENTS_NAV_ITEMS,
  isDocumentsModule,
} from "@/lib/nav/documents-nav";

/**
 * The Documents module's boundary and its rail.
 *
 * The boundary is what the shell uses to swap in the module's own rail, and the
 * items are what the shell then draws, so both are tested directly rather than
 * only through a rendered page.
 */
describe("isDocumentsModule", () => {
  it("claims the hub and everything beneath it", () => {
    for (const pathname of [
      "/dashboard/documents",
      "/dashboard/documents/supporting",
      "/dashboard/documents/approved",
      "/dashboard/documents/supporting/42",
    ]) {
      expect(isDocumentsModule(pathname)).toBe(true);
    }
  });

  it("leaves sibling modules and lookalike paths alone", () => {
    for (const pathname of [
      "/dashboard",
      "/dashboard/leave",
      "/dashboard/workflows",
      "/dashboard/teams",
      // A prefix is not a boundary: the sibling must not be swallowed.
      "/dashboard/documents-extra",
    ]) {
      expect(isDocumentsModule(pathname)).toBe(false);
    }
  });
});

describe("DOCUMENTS_NAV_ITEMS", () => {
  it("lists the hub and its two lists, in order", () => {
    expect(DOCUMENTS_NAV_ITEMS.map((item) => [item.label, item.href])).toEqual([
      ["Dashboard", "/dashboard/documents"],
      ["Supporting Documents", "/dashboard/documents/supporting"],
      ["Approved Documents", "/dashboard/documents/approved"],
    ]);
  });

  it("marks exactly the deepest matching item active for a path", () => {
    const cases: ReadonlyArray<readonly [string, string]> = [
      ["/dashboard/documents", "Dashboard"],
      ["/dashboard/documents/supporting", "Supporting Documents"],
      ["/dashboard/documents/supporting/9", "Supporting Documents"],
      ["/dashboard/documents/approved", "Approved Documents"],
      ["/dashboard/documents/approved/9", "Approved Documents"],
    ];
    for (const [pathname, expected] of cases) {
      const active = DOCUMENTS_NAV_ITEMS.filter((item) =>
        item.match(pathname),
      ).map((item) => item.label);
      expect(active).toEqual([expected]);
    }
  });
});
