import { describe, expect, it, vi } from "vitest";

import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { approverRolePeople } from "@/lib/delegations-client";
import { makeEmployee } from "@/lib/employees/__fixtures__";

// The token plumbing is not what this is about: mocking the read keeps the
// test on the contract that matters, which is what happens when it fails.
vi.mock("@/lib/api-client", () => ({
  apiClient: vi.fn(),
}));

const { apiClient } = await import("@/lib/api-client");

describe("loadApprovalCapabilities", () => {
  it("reports the server's answer", async () => {
    vi.mocked(apiClient).mockResolvedValue({
      is_approver: true,
      pending_count: 4,
    });

    expect(await loadApprovalCapabilities()).toEqual({
      is_approver: true,
      pending_count: 4,
    });
    expect(apiClient).toHaveBeenCalledWith(
      "/api/v1/approvals/capabilities/"
    );
  });

  it("returns null when the read fails, so callers fail closed", async () => {
    vi.mocked(apiClient).mockRejectedValue(new Error("offline"));

    expect(await loadApprovalCapabilities()).toBeNull();
  });

  it("returns null on a refusal rather than treating it as standing", async () => {
    vi.mocked(apiClient).mockRejectedValue(new Error("API error: 403"));

    expect(await loadApprovalCapabilities()).toBeNull();
  });
});

describe("approverRolePeople", () => {
  it("keeps people who hold an approver position, whatever their account role", () => {
    const people = [
      makeEmployee({ id: 1, full_name: "Dean", role: "employee", approver_roles: ["dean"] }),
      makeEmployee({ id: 2, full_name: "HOD", role: "approver", approver_roles: ["hod"] }),
      makeEmployee({ id: 3, full_name: "Staff", role: "hr", approver_roles: [] }),
      makeEmployee({ id: 4, full_name: "Former", role: "employee", approver_roles: ["hod"], is_active: false }),
    ];

    expect(approverRolePeople(people).map((person) => person.full_name)).toEqual([
      "Dean",
      "HOD",
    ]);
  });
});
