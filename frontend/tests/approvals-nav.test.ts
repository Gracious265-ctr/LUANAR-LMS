import { describe, expect, it } from "vitest";

import { approvalsNavItems, isApprovalsModule } from "@/lib/nav/approvals-nav";

/**
 * The Approvals module's boundary and its rail.
 *
 * The boundary is what the shell uses to swap in the module's own rail, and the
 * items are what the shell then draws, so both are tested directly rather than
 * only through a rendered page.
 */
describe("isApprovalsModule", () => {
  it("claims the queue, the cover directory, and everything beneath them", () => {
    for (const pathname of [
      "/dashboard/approvals",
      "/dashboard/approvals/42",
      "/dashboard/cover",
      "/dashboard/cover/42",
    ]) {
      expect(isApprovalsModule(pathname)).toBe(true);
    }
  });

  it("leaves sibling modules and lookalike paths alone", () => {
    for (const pathname of [
      "/dashboard",
      "/dashboard/account",
      "/dashboard/teams",
      "/dashboard/leave",
      // A prefix is not a boundary: the sibling must not be swallowed.
      "/dashboard/approvals-extra",
      "/dashboard/cover-page",
    ]) {
      expect(isApprovalsModule(pathname)).toBe(false);
    }
  });
});

describe("approvalsNavItems", () => {
  it("lists the queue, badged with the resolved count", () => {
    const items = approvalsNavItems({
      pendingApprovals: 4,
      canRequestCover: false,
    });

    expect(items.map((item) => [item.label, item.href, item.badge])).toEqual([
      ["Approvals", "/dashboard/approvals", 4],
    ]);
  });

  it("adds the cover request only for a viewer who may make one", () => {
    const withCover = approvalsNavItems({
      pendingApprovals: 0,
      canRequestCover: true,
    });
    expect(withCover.map((item) => item.label)).toEqual([
      "Approvals",
      "Request Cover",
    ]);

    const withoutCover = approvalsNavItems({
      pendingApprovals: 0,
      canRequestCover: false,
    });
    expect(withCover.map((item) => item.label)).toContain("Request Cover");
    expect(withoutCover.map((item) => item.label)).not.toContain("Request Cover");
  });

  it("marks exactly one item active for a path", () => {
    const items = approvalsNavItems({
      pendingApprovals: 0,
      canRequestCover: true,
    });
    const cases: ReadonlyArray<readonly [string, string]> = [
      ["/dashboard/approvals", "Approvals"],
      ["/dashboard/approvals/42", "Approvals"],
      ["/dashboard/cover", "Request Cover"],
      ["/dashboard/cover/9", "Request Cover"],
    ];
    for (const [pathname, expected] of cases) {
      const active = items.filter((item) => item.match(pathname)).map((item) => item.label);
      expect(active).toEqual([expected]);
    }
  });
});
