import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyPlan,
  cancelPlan,
  createPlan,
  getPlan,
  getScopeOptions,
  getTeamPlans,
  listPlans,
} from "@/lib/plans/service";
import { makePlan, makeScope } from "@/lib/plans/__fixtures__";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(impl: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const spy = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(impl(String(input), init))
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listPlans", () => {
  it("unwraps a paginated response to the plan array", async () => {
    const plan = makePlan();
    mockFetch(() =>
      jsonResponse({ count: 1, next: null, previous: null, results: [plan] })
    );

    await expect(listPlans()).resolves.toEqual([plan]);
  });

  it("accepts an unpaginated array too", async () => {
    const plan = makePlan();
    mockFetch(() => jsonResponse([plan]));
    await expect(listPlans()).resolves.toEqual([plan]);
  });

  it("surfaces the backend detail on failure", async () => {
    mockFetch(() => jsonResponse({ detail: "Not authenticated" }, 401));
    await expect(listPlans()).rejects.toThrow("Not authenticated");
  });
});

describe("createPlan", () => {
  it("POSTs the body as JSON to the plans proxy", async () => {
    const seen: { url: string; init?: RequestInit }[] = [];
    mockFetch((url, init) => {
      seen.push({ url, init });
      return jsonResponse(makePlan());
    });

    const input = {
      leave_type: 2,
      planned_start_date: "2026-11-02",
      planned_end_date: "2026-11-06",
      notes: "Family trip",
    };
    await createPlan(input);

    expect(seen[0].url).toBe("/api/plans/");
    expect(seen[0].init?.method).toBe("POST");
    expect(seen[0].init?.body).toBe(JSON.stringify(input));
  });

  it("passes an overlap warning straight through", async () => {
    mockFetch(() => jsonResponse(makePlan({ overlap_warning: "Overlaps a teammate" })));
    const plan = await createPlan({
      leave_type: 1,
      planned_start_date: "2026-11-02",
      planned_end_date: "2026-11-06",
    });
    expect(plan.overlap_warning).toBe("Overlaps a teammate");
  });
});

describe("getPlan", () => {
  it("requests the id-scoped path", async () => {
    const spy = mockFetch(() => jsonResponse(makePlan({ id: "abc" })));
    await getPlan("abc");
    expect(spy.mock.calls[0][0]).toBe("/api/plans/abc/");
  });
});

describe("cancelPlan", () => {
  it("DELETEs and tolerates a 204 with no body", async () => {
    const spy = mockFetch(() => new Response(null, { status: 204 }));
    await expect(cancelPlan("abc")).resolves.toBeUndefined();
    expect(spy.mock.calls[0][1]?.method).toBe("DELETE");
  });
});

describe("applyPlan", () => {
  it("POSTs to the apply action and returns the application id", async () => {
    const spy = mockFetch(() => jsonResponse({ application_id: "draft-9" }));
    await expect(applyPlan("abc")).resolves.toEqual({ application_id: "draft-9" });
    expect(spy.mock.calls[0][0]).toBe("/api/plans/abc/apply/");
    expect(spy.mock.calls[0][1]?.method).toBe("POST");
  });

  it("passes a converted-plan conflict through as an error", async () => {
    mockFetch(() => jsonResponse({ detail: "This plan has already been applied." }, 409));
    await expect(applyPlan("abc")).rejects.toThrow(
      "This plan has already been applied."
    );
  });
});

describe("getScopeOptions", () => {
  it("returns the scope array", async () => {
    const scopes = [makeScope()];
    mockFetch(() => jsonResponse(scopes));
    await expect(getScopeOptions()).resolves.toEqual(scopes);
  });
});

describe("getTeamPlans", () => {
  it("forwards scope and month as query params", async () => {
    const spy = mockFetch(() => jsonResponse({ results: [] }));
    await getTeamPlans({ scope: "team:3", month: "2026-11" });

    const url = new URL(String(spy.mock.calls[0][0]));
    expect(url.pathname).toBe("/api/plans/team/");
    expect(url.searchParams.get("scope")).toBe("team:3");
    expect(url.searchParams.get("month")).toBe("2026-11");
  });

  it("omits the params when not given", async () => {
    const spy = mockFetch(() => jsonResponse({ results: [] }));
    await getTeamPlans();
    const url = new URL(String(spy.mock.calls[0][0]));
    expect(url.search).toBe("");
  });
});
