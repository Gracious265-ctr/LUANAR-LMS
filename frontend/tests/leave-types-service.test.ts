import { beforeEach, describe, expect, it, vi } from "vitest";

import { getLeaveTypes } from "@/lib/services/leaveTypes";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

function okResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getLeaveTypes", () => {
  it("GETs the leave-types proxy and maps snake_case to camelCase", async () => {
    fetchMock.mockResolvedValue(
      okResponse([
        {
          id: 1,
          code: "annual",
          name: "Annual leave",
          max_duration_days: 30,
          requires_supporting_document: false,
        },
        {
          id: 2,
          code: "maternity",
          name: "Maternity leave",
          max_duration_days: 90,
          requires_supporting_document: true,
        },
      ])
    );

    const result = await getLeaveTypes();

    expect(result).toEqual([
      {
        id: 1,
        code: "annual",
        name: "Annual leave",
        requiresDocuments: false,
        maxDurationDays: 30,
      },
      {
        id: 2,
        code: "maternity",
        name: "Maternity leave",
        requiresDocuments: true,
        maxDurationDays: 90,
      },
    ]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/leave/leave-types/");
    expect(init).toMatchObject({ credentials: "include" });
  });

  it("throws when the request fails", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 500 }));

    await expect(getLeaveTypes()).rejects.toThrow("Failed to fetch leave types");
  });
});