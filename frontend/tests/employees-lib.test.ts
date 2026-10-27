import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listUnassignedEmployees } from "@/lib/employees";
import type { EmployeeListResponse } from "@/lib/employees";

vi.mock("@/lib/api-client", () => ({
  apiClient: vi.fn(),
  apiClientUrl: vi.fn(),
}));

import { apiClient, apiClientUrl } from "@/lib/api-client";

function pageResponse(results: unknown[]): EmployeeListResponse {
  return { count: results.length, next: null, previous: null, results: results as never };
}

describe("listUnassignedEmployees", () => {
  beforeEach(() => {
    vi.mocked(apiClient).mockResolvedValue(pageResponse([]));
    vi.mocked(apiClientUrl).mockResolvedValue(pageResponse([]));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("asks for team=none with no added scoping", async () => {
    await listUnassignedEmployees();

    expect(apiClient).toHaveBeenCalledWith("/api/v1/employees/?team=none");
  });

  it("passes the team's category so the roster matches the team's kind", async () => {
    await listUnassignedEmployees("academic");

    expect(apiClient).toHaveBeenCalledWith(
      "/api/v1/employees/?team=none&category=academic"
    );
  });

  it("keeps every wide approver out of a roster's candidates", async () => {
    await listUnassignedEmployees("administration", true);

    expect(apiClient).toHaveBeenCalledWith(
      "/api/v1/employees/?team=none&category=administration&not_wide_holder=1"
    );
  });

  it("still pages through every candidate the filter returns", async () => {
    vi.mocked(apiClient).mockResolvedValue({
      count: 2,
      next: "https://lms.test/api/v1/employees/?team=none&page=2",
      previous: null,
      results: [{ id: 1 } as never],
    });
    vi.mocked(apiClientUrl).mockResolvedValue(pageResponse([{ id: 2 }]));
    vi.mocked(apiClientUrl).mockResolvedValueOnce(pageResponse([{ id: 2 }]));

    const rows = await listUnassignedEmployees("academic", true);

    expect(apiClientUrl).toHaveBeenCalledWith(
      "https://lms.test/api/v1/employees/?team=none&page=2"
    );
    expect(rows.map((row) => row.id)).toEqual([1, 2]);
  });
});