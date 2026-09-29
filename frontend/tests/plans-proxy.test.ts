import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";
import { GET as plansGET } from "@/app/api/plans/route";
import { POST as submitPOST } from "@/app/api/plans/[id]/submit/route";
import { GET as adminGET } from "@/app/api/plans/admin/route";
import { GET as approvalsGET } from "@/app/api/plans/approvals/route";

function mockCookies(access: string | undefined, refresh: string | undefined) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) =>
      ({ access_token: access, refresh_token: refresh }[name] !== undefined
        ? { name, value: ({ access_token: access, refresh_token: refresh } as Record<string, string>)[name] }
        : undefined),
  } as never);
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function request(url: string): Request {
  return new Request(`http://localhost${url}`);
}

describe("plans proxy routes", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    mockCookies("access-1", "refresh-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockReset();
  });

  it("passes an allow-listed scope to the plans list", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { scope: "team", count: 1, results: [] })
    );

    const res = await plansGET(request("/api/plans/?scope=team"));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/plans/?scope=team"),
      expect.anything()
    );
    expect(res.status).toBe(200);
  });

  it("falls back to mine for an unknown scope", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { scope: "mine", count: 0, results: [] })
    );

    const res = await plansGET(request("/api/plans/?scope=hack"));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/plans/?scope=mine"),
      expect.anything()
    );
    expect(res.status).toBe(200);
  });

  it("forwards the submit POST to the backend", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { id: "plan-1" }));

    await submitPOST(request("/api/plans/plan-1/submit/"), {
      params: Promise.resolve({ id: "plan-1" }),
    });

    const call = vi.mocked(fetch).mock.calls[0];
    expect(String(call[0])).toContain("/api/v1/plans/plan-1/submit/");
    expect(call[1]).toMatchObject({ method: "POST" });
  });

  it("drops non-allow-listed plan status filters on the admin list", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { count: 0, next: null, previous: null, results: [] })
    );

    await adminGET(request("/api/plans/admin/?status=banana&page=1"));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/plans/admin/?page=1"),
      expect.anything()
    );
    expect(String(vi.mocked(fetch).mock.calls[0][0])).not.toContain(
      "status=banana"
    );
  });

  it("passes an allow-listed block status on the admin list", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { count: 0, next: null, previous: null, results: [] })
    );

    await adminGET(request("/api/plans/admin/?block_status=reserved&page=1"));

    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain(
      "block_status=reserved"
    );
  });

  it("defaults the approvals tab to pending", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { tab: "pending", count: 0, results: [] })
    );

    const res = await approvalsGET(request("/api/plans/approvals/"));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/plans/approvals/?tab=pending"),
      expect.anything()
    );
    expect(res.status).toBe(200);
  });
});