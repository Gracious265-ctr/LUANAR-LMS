import { afterEach, describe, expect, it, vi } from "vitest";

import { listMemberCandidates } from "@/lib/teams-client";
import { listActiveApproverRoles } from "@/lib/approver-roles-client";

/**
 * The two reads a team manager reaches instead of the HR-only directory and
 * role endpoints. These pin the routes so a rename cannot quietly send the
 * manager back to a URL the backend refuses.
 */
describe("manager-scoped reads", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reads the roster's candidates through the team's own route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify([{ id: 1, email: "a@e2e.luanar" }]), {
          status: 200,
        })
      );

    const rows = await listMemberCandidates(7);

    expect(fetchMock).toHaveBeenCalledWith("/api/hr/teams/7/member-candidates/");
    expect(rows).toEqual([{ id: 1, email: "a@e2e.luanar" }]);
  });

  it("reads the read-only role list off the eligible-approver-roles route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify([{ id: 1, code: "supervisor" }]), {
          status: 200,
        })
      );

    const roles = await listActiveApproverRoles();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/hr/teams/eligible-approver-roles/"
    );
    expect(roles).toEqual([{ id: 1, code: "supervisor" }]);
  });

  it("surfaces the backend's refusal rather than an empty list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "You do not manage a team." }), {
        status: 403,
      })
    );

    await expect(listActiveApproverRoles()).rejects.toThrow(
      "You do not manage a team."
    );
  });
});
