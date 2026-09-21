import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";
import { apiFetch } from "@/app/api/_lib/api-fetch";

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

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockReset();
  });

  it("forwards with the access token and returns the JSON body", async () => {
    mockCookies("access-1", "refresh-1");
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { results: [] })
    );

    const res = await apiFetch("GET", "employees/");

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/employees/"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer access-1" }),
      })
    );
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({ results: [] });
  });

  it("refreshes once and retries on a 401 response", async () => {
    mockCookies("access-expired", "refresh-1");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { access: "refreshed-access" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }));

    const res = await apiFetch("GET", "employees/");

    expect(fetch).toHaveBeenCalledTimes(3);
    const retried = vi.mocked(fetch).mock.calls[2];
    expect(retried[1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer refreshed-access" }),
    });
    expect(res.status).toBe(200);
    expect(res.cookies.get("access_token")?.value).toBe("refreshed-access");
  });

  it("returns 401 when the refresh also fails", async () => {
    mockCookies("access-expired", "refresh-expired");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Bad token" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Refresh failed" }));

    const res = await apiFetch("GET", "employees/");

    expect(res.status).toBe(401);
    expect(res.cookies.get("access_token")).toBeUndefined();
  });

  it("refreshes up front when only the refresh cookie is present", async () => {
    mockCookies(undefined, "refresh-1");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(200, { access: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }));

    const res = await apiFetch("GET", "employees/");

    expect(fetch).toHaveBeenCalledTimes(2);
    const forwarded = vi.mocked(fetch).mock.calls[1];
    expect(forwarded[1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer fresh-access" }),
    });
    expect(res.cookies.get("access_token")?.value).toBe("fresh-access");
  });

  it("returns 401 Unauthorized when no token is present", async () => {
    mockCookies(undefined, undefined);

    const res = await apiFetch("GET", "employees/");

    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ detail: "Unauthorized" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("handles 204 no-content responses", async () => {
    mockCookies("access-1", "refresh-1");
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    const res = await apiFetch("DELETE", "employees/1/");

    expect(res.status).toBe(204);
  });
});