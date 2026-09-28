import { describe, expect, it } from "vitest";

import { canRequestCover } from "@/lib/delegations";
import type { ApprovalCapabilities } from "@/lib/approvals/types";

function capabilities(
  overrides: Partial<ApprovalCapabilities> = {}
): ApprovalCapabilities {
  return { is_approver: true, pending_count: 0, ...overrides };
}

describe("canRequestCover", () => {
  it("allows anyone the server reports as an approver", () => {
    // HR is admitted by the same answer, and so is a colleague whose account
    // reads `employee` but who holds an approver position on a team.
    expect(canRequestCover(capabilities())).toBe(true);
    expect(canRequestCover(capabilities({ pending_count: 2 }))).toBe(true);
  });

  it("rejects a caller the server does not recognise as an approver", () => {
    expect(canRequestCover(capabilities({ is_approver: false }))).toBe(false);
  });

  it("rejects a caller whose standing could not be read", () => {
    // Fail closed: an unknown caller is sent to the dashboard, not shown a
    // cover form the API would then refuse.
    expect(canRequestCover(null)).toBe(false);
  });
});
