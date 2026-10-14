/**
 * The password-change proxy.
 *
 * A thin wrapper by design — the same single call the other authenticated
 * writes make — so the tests are narrow: does it hit the right Django path with
 * the body intact, and does a refusal arrive as a refusal rather than being
 * flattened into a 500 on the way through? The cookie handling that a proxy
 * could plausibly get wrong belongs to `apiFetch`, which is covered by
 * tests/api-fetch.test.ts; re-testing it here would only pin the helper.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";
import { POST } from "@/app/api/auth/password-change/route";

const DJANGO = process.env.DJANGO_API_URL || "http://localhost:8000";

function mockCookies(access: string | undefined, refresh: string | undefined) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) => {
      const values: Record<string, string> = {
        access_token: access as string,
        refresh_token: refresh as string,
      };
      return name in values ? { name, value: values[name] } : undefined;
    },
  } as never);
}

function jsonRequest(body: unknown) {
  return new Request("http://localhost:3000/api/auth/password-change", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const PAYLOAD = {
  current_password: "current pass phrase 7",
  new_password: "a whole new pass phrase 9",
  confirm_password: "a whole new pass phrase 9",
};

describe("POST /api/auth/password-change", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCookies("an-access-token", undefined);
  });

  it("forwards to the Django password-change endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Password changed." }));

    await POST(jsonRequest(PAYLOAD));

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/auth/password-change/`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(PAYLOAD),
      }),
    );
  });

  it("carries the caller's access token, since this one is authenticated", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "ok" }));

    await POST(jsonRequest(PAYLOAD));

    const [, init] = fetchSpy.mock.calls[0];
    expect((init as RequestInit).headers).toEqual(
      expect.objectContaining({ Authorization: "Bearer an-access-token" }),
    );
  });

  it("passes a refusal through with its real status and body", async () => {
    // A wrong current password must arrive as a 400 the form can attribute to a
    // field. Rewriting it here would turn a fixable mistake into a generic
    // failure.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Your current password is not correct." }, 400),
    );

    const response = await POST(
      jsonRequest({ ...PAYLOAD, current_password: "wrong" }),
    );

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      detail: "Your current password is not correct.",
    });
  });

  it("passes a keyed validator error through intact", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ confirm_password: ["The two passwords do not match."] }, 400),
    );

    const response = await POST(jsonRequest(PAYLOAD));

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      confirm_password: ["The two passwords do not match."],
    });
  });

  it("returns 401 when the caller has no session at all", async () => {
    // Reached when someone posts to the proxy with no cookies, which the
    // dashboard guard cannot intercept because this is not a page request.
    mockCookies(undefined, undefined);

    const response = await POST(jsonRequest(PAYLOAD));

    expect(response.status).toBe(401);
  });

  it("rejects a refresh token that the password change has already killed", async () => {
    // The end-to-end version of "sign out everywhere": an old refresh token
    // presented after the change cannot mint a new access token, and the
    // proxy's single retry has nothing to retry with.
    mockCookies(undefined, "an-old-refresh-token");

    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Unauthorised" }, 401));

    const response = await POST(jsonRequest(PAYLOAD));

    expect(response.status).toBe(401);
    expect(fetchSpy).toHaveBeenCalled();
  });
});
