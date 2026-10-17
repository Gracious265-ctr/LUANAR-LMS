import { describe, expect, it } from "vitest";

import {
  PLAN_STATUS_META,
  isActionable,
  isHistory,
  planSortKey,
  planStatusLabel,
} from "@/lib/plans/labels";
import type { LeavePlanStatus } from "@/lib/plans/types";
import { makePlan } from "@/lib/plans/__fixtures__";

const ALL_STATUSES: LeavePlanStatus[] = [
  "upcoming",
  "notified",
  "missed",
  "converted",
  "cancelled",
];

describe("PLAN_STATUS_META", () => {
  it("covers every status the backend can emit", () => {
    for (const status of ALL_STATUSES) {
      expect(PLAN_STATUS_META[status]).toBeDefined();
      expect(PLAN_STATUS_META[status].label).not.toHaveLength(0);
    }
  });

  it("reads 'notified' as the action prompt, not a neutral state", () => {
    expect(PLAN_STATUS_META.notified.label).toBe("Ready to apply");
    expect(PLAN_STATUS_META.notified.badgeTone).toBe("pending");
  });
});

describe("planStatusLabel", () => {
  it("returns the human label for a known status", () => {
    expect(planStatusLabel("missed")).toBe("Missed");
  });
});

describe("isActionable", () => {
  it("treats both live states as actionable", () => {
    // Apply Now is available from creation (spec 2.3), not only once a reminder
    // has fired, so `upcoming` must be actionable too.
    expect(isActionable(makePlan({ status: "upcoming" }))).toBe(true);
    expect(isActionable(makePlan({ status: "notified" }))).toBe(true);
  });

  it("treats every finished state as not actionable", () => {
    for (const status of ["missed", "converted", "cancelled"] as const) {
      expect(isActionable(makePlan({ status }))).toBe(false);
    }
  });
});

describe("isHistory", () => {
  it("is the complement of isActionable", () => {
    for (const status of ALL_STATUSES) {
      const plan = makePlan({ status });
      expect(isHistory(plan)).toBe(!isActionable(plan));
    }
  });
});

describe("planSortKey", () => {
  it("orders by start date then creation time", () => {
    const a = makePlan({ planned_start_date: "2026-11-01", created_at: "2026-10-01T00:00:00Z" });
    const b = makePlan({ planned_start_date: "2026-11-02", created_at: "2026-09-01T00:00:00Z" });
    expect(planSortKey(a) < planSortKey(b)).toBe(true);
  });
});
