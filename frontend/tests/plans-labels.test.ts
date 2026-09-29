import { describe, expect, it } from "vitest";

import {
  BLOCK_STATUS_META,
  PLAN_ACTION_META,
  PLAN_STATUS_META,
  planDecisionVerb,
} from "@/lib/plans/labels";
import {
  makeApprovalList,
  makeBlock,
  makeCapabilities,
  makeMeta,
  makePendingConfirmations,
  makePlanDetail,
  makePlanRow,
} from "@/lib/plans/__fixtures__";

describe("plans labels", () => {
  it("covers every plan status", () => {
    expect(Object.keys(PLAN_STATUS_META).sort()).toEqual([
      "approved",
      "draft",
      "rejected",
      "submitted",
    ]);
  });

  it("covers every block status", () => {
    expect(Object.keys(BLOCK_STATUS_META).sort()).toEqual([
      "confirmed",
      "lapsed",
      "proposed",
      "released",
      "reserved",
    ]);
  });

  it("covers every plan decision action", () => {
    expect(Object.keys(PLAN_ACTION_META).sort()).toEqual(["approve", "reject"]);
    expect(planDecisionVerb("approve")).toBe("approve");
    expect(planDecisionVerb("reject")).toBe("reject");
  });
});

describe("plans fixtures", () => {
  it("builds consistent row, detail, capability and queue fixtures", () => {
    expect(makeMeta().status).toBe("approved");
    expect(makeBlock().can_confirm).toBe(true);
    expect(makePlanRow().employee_name).toBe("Mphatso Kachale");
    expect(makePlanDetail().blocks).toHaveLength(2);
    expect(makeCapabilities().approver_pending_count).toBe(2);
    expect(makePendingConfirmations().count).toBe(1);
    expect(makeApprovalList().tab).toBe("pending");
  });
});