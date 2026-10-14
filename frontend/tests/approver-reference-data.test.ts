import { describe, expect, it, vi } from "vitest";

import {
  listApproverRoles,
  listRoleAssignments,
} from "@/lib/approver-roles";
import { listTeams } from "@/lib/teams";

vi.mock("@/lib/api-client", () => ({
  apiClient: vi.fn(),
  apiClientUrl: vi.fn(),
}));

const { apiClientUrl } = await import("@/lib/api-client");

function page<T>(results: T[], next: string | null) {
  return { count: results.length, next, previous: null, results };
}

describe("paginated reference data", () => {
  it("reads every page of roles, not just the first", async () => {
    vi.mocked(apiClientUrl)
      .mockResolvedValueOnce(
        page([{ id: 1, code: "hod" }], "http://django/api/v1/approver-roles/?page=2")
      )
      .mockResolvedValueOnce(
        page([{ id: 2, code: "dean" }], "http://django/api/v1/approver-roles/?page=3")
      )
      .mockResolvedValueOnce(page([{ id: 3, code: "registrar" }], null));

    const roles = await listApproverRoles();

    expect(roles.map((role) => role.code)).toEqual(["hod", "dean", "registrar"]);
    // The `next` link is absolute, so it has to be used as given rather than
    // having the API origin prefixed a second time.
    expect(apiClientUrl).toHaveBeenNthCalledWith(
      2,
      "http://django/api/v1/approver-roles/?page=2"
    );
  });

  it("asks for retired roles only when asked", async () => {
    vi.mocked(apiClientUrl).mockResolvedValue(page([], null));

    await listApproverRoles();
    expect(apiClientUrl).toHaveBeenCalledWith("/api/v1/approver-roles/");

    await listApproverRoles(true);
    expect(apiClientUrl).toHaveBeenCalledWith(
      "/api/v1/approver-roles/?include_inactive=1"
    );
  });

  it("narrows holdings to one role when asked", async () => {
    vi.mocked(apiClientUrl).mockResolvedValue(page([], null));

    await listRoleAssignments(4);
    expect(apiClientUrl).toHaveBeenCalledWith(
      "/api/v1/role-assignments/?role=4"
    );
  });

  it("reads every page of teams", async () => {
    vi.mocked(apiClientUrl)
      .mockResolvedValueOnce(
        page([{ id: 1, name: "Bunda" }], "http://django/api/v1/teams/?page=2")
      )
      .mockResolvedValueOnce(page([{ id: 2, name: "Registry" }], null));

    const teams = await listTeams();

    expect(teams.map((team) => team.name)).toEqual(["Bunda", "Registry"]);
  });
});
