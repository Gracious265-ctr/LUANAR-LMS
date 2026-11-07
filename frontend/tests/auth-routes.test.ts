import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { POST as refresh } from "@/app/api/auth/refresh/route";

function mockCookies(values: Record<string, string | undefined>) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) =>
      values[name] !== undefined
        ? { name, value: values[name] as string }
        : undefined,
  } as never);
}

describe("auth route handlers", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.mocked(cookies).mockReset();
  });

  it("revokes the refresh token at Django before clearing cookies on sign-out", async () => {
    mockCookies({ refresh_token: "refresh-1" });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    const response = await logout();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/logout/"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ refresh: "refresh-1" }),
      })
    );
    const header = response.headers.get("set-cookie") ?? "";
    expect(header).toContain("access_token=");
    expect(header).toContain("refresh_token=");
    expect(header).toContain("Max-Age=0");
  });

  it("still clears the cookies when the revocation cannot be delivered", async () => {
    mockCookies({ refresh_token: "refresh-1" });
    vi.mocked(fetch).mockRejectedValueOnce(new Error("django is down"));

    const response = await logout();

    expect(response.status).toBe(200);
    const header = response.headers.get("set-cookie") ?? "";
    expect(header).toContain("refresh_token=");
  });

  it("drops both cookies when the refresh token is rejected", async () => {
    mockCookies({ access_token: "stale", refresh_token: "expired" });
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Token is expired" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );

    const response = await refresh();

    expect(response.status).toBe(401);
    const header = response.headers.get("set-cookie") ?? "";
    expect(header).toContain("access_token=");
    expect(header).toContain("refresh_token=");
    expect(header).toContain("Max-Age=0");
  });
});

describe("login route (CSRF)", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function loginRequest(origin?: string): Request {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      host: "leave.example.edu",
    };
    if (origin) headers.origin = origin;
    return new Request("https://leave.example.edu/api/auth/login", {
      method: "POST",
      headers,
      body: JSON.stringify({ email: "a@luanar.ac.mw", password: "secret123" }),
    });
  }

  it("refuses a browser request from another site", async () => {
    // Sign-in needs no cookie of its own, so SameSite cannot stop a hostile
    // page from POSTing the attacker's credentials and having the victim's
    // browser accept the resulting session.
    const response = await login(loginRequest("https://evil.example"));

    expect(response.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("allows a same-origin sign-in and sets both cookies", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ access: "a1", refresh: "r1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const response = await login(loginRequest("https://leave.example.edu"));

    expect(response.status).toBe(200);
    const header = response.headers.get("set-cookie") ?? "";
    expect(header).toContain("access_token=a1");
    expect(header).toContain("refresh_token=r1");
    expect(header).toContain("HttpOnly");
  });

  it("allows a non-browser caller that sends no Origin header", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ access: "a1", refresh: "r1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const response = await login(loginRequest());

    expect(response.status).toBe(200);
  });
});
