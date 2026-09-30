import { describe, expect, it } from "vitest";

import {
  ACTION_META,
  BLOCK_STATUS_META,
  PLAN_STATUS_META,
  STAGE_STATUS_META,
  candidateSummary,
  planVerb,
  restrictionLabel,
  restrictionTitle,
} from "@/lib/plans/labels";
import { formatPeriod, formatWorkingDays } from "@/lib/plans/format";
import type { BlockStatus, PlanStageStatus, PlanStatus } from "@/lib/plans/types";

describe("status label maps", () => {
  it("names every plan status the API can return", () => {
    const statuses: PlanStatus[] = ["draft", "submitted", "approved", "rejected"];

    for (const status of statuses) {
      const meta = PLAN_STATUS_META[status];
      expect(meta.label).toBeTruthy();
      expect(meta.icon).toBeTruthy();
      expect(meta.badgeTone).toBeTruthy();
    }
  });

  it("names every block status the API can return", () => {
    const statuses: BlockStatus[] = [
      "proposed",
      "reserved",
      "confirmed",
      "lapsed",
      "released",
    ];

    for (const status of statuses) {
      expect(BLOCK_STATUS_META[status].label).toBeTruthy();
    }
  });

  it("has no skipped stage, because a section is never bypassed", () => {
    const statuses = Object.keys(STAGE_STATUS_META) as PlanStageStatus[];

    expect(statuses).toEqual(["waiting", "pending", "approved", "rejected"]);
    expect(statuses).not.toContain("skipped");
  });

  it("offers approve and reject only: a plan is not editable", () => {
    expect(Object.keys(ACTION_META)).toEqual(["approve", "reject"]);
  });
});

describe("planVerb", () => {
  it("reads as the outcome that just happened", () => {
    expect(planVerb("approved")).toBe("approved");
    expect(planVerb("rejected")).toBe("rejected");
    expect(planVerb("submitted")).toBe("submitted for approval");
    expect(planVerb("draft")).toBe("saved");
  });
});

describe("restrictionLabel", () => {
  it("names the stage holding the plan when it is not the caller's turn", () => {
    expect(restrictionLabel("not_current_stage", "HOD", "submitted")).toContain(
      "HOD"
    );
  });

  it("says so plainly when no stage is open", () => {
    expect(restrictionLabel("not_current_stage", null, "submitted")).toBe(
      "This plan has not reached your stage yet."
    );
  });

  it("explains a refusal on somebody's own plan", () => {
    expect(restrictionLabel("self_plan", null, "submitted")).toBe(
      "You cannot decide on your own plan."
    );
  });

  it("names the closed status instead of leaving the panel silent", () => {
    expect(restrictionLabel("plan_closed", null, "approved")).toContain(
      "approved"
    );
  });

  it("falls back to a plain refusal for an unknown reason", () => {
    expect(restrictionLabel(null, null, null)).toBe(
      "You are not allowed to decide on this plan."
    );
  });
});

describe("restrictionTitle", () => {
  it("titles the dialog by the action", () => {
    expect(restrictionTitle("approve")).toBe("Approve plan");
    expect(restrictionTitle("reject")).toBe("Reject plan");
  });
});

describe("candidateSummary", () => {
  it("names the person who claimed the stage", () => {
    expect(
      candidateSummary({
        is_claimed: true,
        approver_name: "Chikondi Mbewe",
        eligible_approvers: [{ name: "Chikondi Mbewe" }, { name: "A. Banda" }],
      })
    ).toBe("Chikondi Mbewe");
  });

  it("lists the candidates of an unclaimed stage", () => {
    expect(
      candidateSummary({
        is_claimed: false,
        approver_name: "",
        eligible_approvers: [{ name: "A. Banda" }, { name: "B. Chirwa" }],
      })
    ).toBe("A. Banda or B. Chirwa");
  });

  it("counts the tail rather than listing a whole section", () => {
    const summary = candidateSummary({
      is_claimed: false,
      approver_name: "",
      eligible_approvers: [
        { name: "A. Banda" },
        { name: "B. Chirwa" },
        { name: "C. Daka" },
        { name: "D. Phiri" },
      ],
    });

    expect(summary).toBe("A. Banda, B. Chirwa and 2 more");
  });

  it("says nobody is available rather than showing an empty list", () => {
    expect(
      candidateSummary({
        is_claimed: false,
        approver_name: "",
        eligible_approvers: [],
      })
    ).toBe("Nobody available");
  });
});

describe("formatPeriod", () => {
  it("collapses the repeated year across a span", () => {
    const period = formatPeriod("2026-10-01", "2026-12-18");

    expect(period).not.toMatch(/2026.*2026/);
    expect(period).toContain("–");
  });

  it("keeps both years when they differ", () => {
    const period = formatPeriod("2026-12-28", "2027-01-08");

    expect(period).toMatch(/2026/);
    expect(period).toMatch(/2027/);
  });

  it("marks an open end rather than printing a blank", () => {
    expect(formatPeriod("2026-10-01", null)).toContain("…");
    expect(formatPeriod(null, "2026-10-01")).toContain("…");
    expect(formatPeriod(null, null)).toBe("—");
  });
});

describe("formatWorkingDays", () => {
  it("agrees in number with its noun", () => {
    expect(formatWorkingDays(1)).toBe("1 working day");
    expect(formatWorkingDays(3)).toBe("3 working days");
  });

  it("is an em dash until the days are computed", () => {
    expect(formatWorkingDays(null)).toBe("—");
    expect(formatWorkingDays(undefined)).toBe("—");
  });
});
