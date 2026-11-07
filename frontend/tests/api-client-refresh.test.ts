import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";
import { apiClient } from "@/lib/api-client";

function mockCookies(access: string | undefined, refresh: string | undefined) {
  const values: Record<string, string | undefined> = {
    access_token: access,
    refresh_token: refresh,
  };
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) =>
      values[name] !== undefined
        ? { name, value: values[name] as string }
        : undefined,
  } as never);
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("server-side API client session handling", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockReset();
  });

  it("refreshes before the request when the access cookie has expired", async () => {
    mockCookies(undefined, "refresh-1");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(200, { access: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }));

    const result = await apiClient<{ id: number }>("/api/v1/auth/me/");

    expect(result).toEqual({ id: 1 });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(vi.mocked(fetch).mock.calls[1][1]).toMatchObject({
      headers: expect.objectContaining({
        Authorization: "Bearer fresh-access",
      }),
    });
  });

  it("refreshes and retries once when a present access token is rejected", async () => {
    mockCookies("expired-access", "refresh-1");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { access: "fresh-access" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }));

    const result = await apiClient<{ id: number }>("/api/v1/auth/me/");

    expect(result).toEqual({ id: 1 });
    expect(vi.mocked(fetch).mock.calls[2][1]).toMatchObject({
      headers: expect.objectContaining({
        Authorization: "Bearer fresh-access",
      }),
    });
  });

  it("does not call the refresh endpoint when there is no refresh cookie", async () => {
    mockCookies(undefined, undefined);
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(401, { detail: "Authentication credentials were not provided." })
    );

    await expect(apiClient("/api/v1/auth/me/")).rejects.toThrow(
      "Authentication credentials were not provided."
    );

    expect(fetch).toHaveBeenCalledTimes(1);
    const headers = vi.mocked(fetch).mock.calls[0][1]?.headers as Record<
      string,
      string
    >;
    expect(headers.Authorization).toBeUndefined();
  });
});

describe("server-side API client failure handling", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockReset();
  });

  it("tries a dead refresh token once, then reports the 401 without a second refresh", async () => {
    mockCookies(undefined, "dead-refresh");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token is invalid" }))
      .mockResolvedValueOnce(
        jsonResponse(401, { detail: "Authentication credentials were not provided." })
      );

    await expect(apiClient("/api/v1/auth/me/")).rejects.toThrow(
      "Authentication credentials were not provided."
    );

    // One refresh attempt (which failed), then the request itself. Retrying the
    // refresh would just repeat the same rejected upstream call.
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
