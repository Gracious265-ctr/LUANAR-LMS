import { describe, expect, it } from "vitest";

import { LEAVE_NAV_ITEMS, isLeaveModule } from "@/lib/nav/leave-nav";

/**
 * The Leave rail, with its newest destination.
 *
 * On Leave is a page inside the Leave module, so the module boundary already
 * claims it; the item is what puts it on the rail and what marks it active.
 */
describe("isLeaveModule", () => {
  it("claims the on-leave page and everything beneath it", () => {
    for (const pathname of [
      "/dashboard/leave/on-leave",
      "/dashboard/leave/on-leave/42",
      "/dashboard/leave",
      "/applications/9",
    ]) {
      expect(isLeaveModule(pathname)).toBe(true);
    }
  });

  it("leaves the launcher and lookalike paths alone", () => {
    for (const pathname of [
      "/",
      "/dashboard",
      "/dashboard/teams",
      // A prefix is not a boundary: the sibling must not be swallowed.
      "/dashboard/leave-extra",
    ]) {
      expect(isLeaveModule(pathname)).toBe(false);
    }
  });
});

describe("LEAVE_NAV_ITEMS", () => {
  it("lists the employee's destinations, in order", () => {
    expect(LEAVE_NAV_ITEMS.map((item) => [item.label, item.href])).toEqual([
      ["Dashboard", "/dashboard/leave"],
      ["My Applications", "/dashboard/leave/applications"],
      ["Drafts", "/dashboard/leave/drafts"],
      ["On Leave", "/dashboard/leave/on-leave"],
      ["New Application", "/dashboard/leave/new"],
    ]);
  });

  it("marks the on-leave page and its subpaths active", () => {
    const item = LEAVE_NAV_ITEMS.find((entry) => entry.label === "On Leave");

    expect(item?.match("/dashboard/leave/on-leave")).toBe(true);
    expect(item?.match("/dashboard/leave/on-leave/42")).toBe(true);
    expect(item?.match("/dashboard/leave/drafts")).toBe(false);
    expect(item?.match("/dashboard/leave/applications")).toBe(false);
  });

  it("marks exactly one item active for each leave path", () => {
    const paths = [
      "/dashboard/leave",
      "/dashboard/leave/applications",
      "/dashboard/leave/drafts",
      "/dashboard/leave/on-leave",
    ];
    for (const pathname of paths) {
      const active = LEAVE_NAV_ITEMS.filter((item) => item.match(pathname));
      expect(active).toHaveLength(1);
    }
  });
});
