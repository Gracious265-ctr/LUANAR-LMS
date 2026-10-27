import { afterEach, describe, expect, it, vi } from "vitest";

import { listMemberCandidates } from "@/lib/teams-client";

const apiClient = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  apiClient,
  apiClientUrl: vi.fn(),
}));

const { listEligibleApproverRoles } = await import("@/lib/approver-roles");

/**
 * The reads a team manager reaches instead of the HR-only directory and role
 * endpoints. These pin the routes so a rename cannot quietly send the manager
 * back to a URL the backend refuses.
 */
describe("manager-scoped reads", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    apiClient.mockReset();
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

  /**
   * The role list is read by a *server* component, so it has to go through the
   * server client. A relative `fetch("/api/hr/…")` has no origin to resolve
   * against on the server: it throws, and the chain form then claims no role
   * exists. This pins the read to `apiClient`, which supplies Django's absolute
   * URL and the caller's token.
   */
  it("reads the eligible role list through the server client", async () => {
    apiClient.mockResolvedValue([{ id: 1, code: "supervisor" }]);

    const roles = await listEligibleApproverRoles();

    expect(apiClient).toHaveBeenCalledWith(
      "/api/v1/teams/eligible-approver-roles/"
    );
    expect(roles).toEqual([{ id: 1, code: "supervisor" }]);
  });

  it("propagates the backend's refusal rather than returning no roles", async () => {
    apiClient.mockRejectedValue(new Error("You do not manage a team."));

    await expect(listEligibleApproverRoles()).rejects.toThrow(
      "You do not manage a team."
    );
  });
});
