// @vitest-environment node
import { describe, expect, it } from "vitest";

import type { LeaveRule } from "@/lib/leave-rules";
import { leaveRuleStatus } from "@/lib/leave-rules";

const currentRule: LeaveRule = {
  id: 1,
  leave_type: 2,
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  max_duration_days: 30,
  eligibility: "",
  min_notice_days: 5,
  requires_supporting_document: false,
  consumes_annual_entitlement: true,
  effective_from: "2026-01-01",
};

describe("leaveRuleStatus", () => {
  it("returns current when the rule is effective on or before today", () => {
    expect(leaveRuleStatus(currentRule, "2026-09-17")).toBe("current");
    expect(leaveRuleStatus(currentRule, "2026-01-01")).toBe("current");
  });

  it("returns upcoming when the rule becomes effective later", () => {
    const upcoming: LeaveRule = {
      ...currentRule,
      id: 2,
      effective_from: "2027-01-01",
    };
    expect(leaveRuleStatus(upcoming, "2026-09-17")).toBe("upcoming");
  });
});