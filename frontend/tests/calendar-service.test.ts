import { describe, expect, it, vi } from "vitest";

import { fetchTeamCalendar } from "@/lib/calendar/service";
import type { TeamCalendarResponse } from "@/lib/calendar/types";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(impl: (url: string) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => impl(String(input)))
  );
}

const PAYLOAD: TeamCalendarResponse = {
  unit_id: 7,
  unit_name: "Finance",
  month: "2026-10",
  team_size: 5,
  conflict_threshold: 2,
  entries: [],
};

describe("fetchTeamCalendar", () => {
  it("requests the team calendar for the month", async () => {
    mockFetch((url) => {
      expect(url).toContain("/api/leave/calendar/team/?");
      expect(url).toContain("unit_id=7");
      expect(url).toContain("month=2026-10");
      return Promise.resolve(jsonResponse(PAYLOAD, 200));
    });
    const result = await fetchTeamCalendar(7, "2026-10");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.unit_name).toBe("Finance");
  });

  it("treats a 404 as not found, not an error", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ detail: "gone" }, 404)));
    const result = await fetchTeamCalendar(7, "2026-10");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("not_found");
  });

  it("surfaces the server message for other failures", async () => {
    mockFetch(() => Promise.resolve(jsonResponse({ detail: "Boom" }, 500)));
    const result = await fetchTeamCalendar(7, "2026-10");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("error");
      expect(result.message).toBe("Boom");
    }
  });

  it("returns a network error when the request rejects", async () => {
    mockFetch(() => Promise.reject(new Error("down")));
    const result = await fetchTeamCalendar(7, "2026-10");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.kind).toBe("error");
  });
});
