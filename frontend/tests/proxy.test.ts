import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { proxy } from "@/proxy";

function tokenWithExpiry(exp: number): string {
  const encode = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none", typ: "JWT" })}.${encode({ exp })}.signature`;
}

function liveToken(minutes = 10): string {
  return tokenWithExpiry(Math.floor(Date.now() / 1000) + minutes * 60);
}

function expiredToken(minutes = 10): string {
  return tokenWithExpiry(Math.floor(Date.now() / 1000) - minutes * 60);
}

function request(path: string, cookies: Record<string, string> = {}) {
  const nextRequest = new NextRequest(`http://localhost:3000${path}`);
  for (const [name, value] of Object.entries(cookies)) {
    nextRequest.cookies.set(name, value);
  }
  return nextRequest;
}

function isNext(response: Response): boolean {
  return response.headers.get("x-middleware-next") === "1";
}

function setCookieHeader(response: Response): string {
  return response.headers.get("set-cookie") ?? "";
}

describe("auth proxy", () => {
  it("sends an anonymous visitor from a protected route to the login page", () => {
    const response = proxy(request("/dashboard"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("lets a live access token through", () => {
    const response = proxy(
      request("/dashboard", { access_token: liveToken() })
    );

    expect(isNext(response)).toBe(true);
  });

  it("keeps the session alive when only the refresh token is live", () => {
    // The access cookie expires after 15 minutes; the refresh cookie lasts a
    // day. Requiring the access cookie made every employee sign in again
    // mid-session even though their refresh token was still valid.
    const response = proxy(
      request("/dashboard", {
        access_token: expiredToken(),
        refresh_token: liveToken(60 * 12),
      })
    );

    expect(isNext(response)).toBe(true);
  });

  it("clears both dead cookies and redirects when neither token is live", () => {
    const response = proxy(
      request("/dashboard", {
        access_token: expiredToken(),
        refresh_token: expiredToken(),
      })
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
    const cookies = setCookieHeader(response);
    expect(cookies).toContain("access_token=");
    expect(cookies).toContain("refresh_token=");
    expect(cookies).toContain("Expires=Thu, 01 Jan 1970");
  });

  it("does not redirect a stale cookie loop from the login page back to the app", () => {
    const response = proxy(
      request("/login", {
        access_token: expiredToken(),
        refresh_token: expiredToken(),
      })
    );

    expect(isNext(response)).toBe(true);
  });

  it("sends an already signed-in visitor away from the login page", () => {
    const response = proxy(
      request("/login", { refresh_token: liveToken(60 * 12) })
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("ignores a cookie whose payload cannot be decoded", () => {
    const response = proxy(
      request("/dashboard", { access_token: "not-a-jwt" })
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("guards /applications/[id], which sits in the dashboard group but not under /dashboard", () => {
    // Route groups do not appear in the URL, so this page is outside the
    // `/dashboard` prefix while still being a signed-in screen.
    const anonymous = proxy(request("/applications/42"));
    expect(anonymous.status).toBe(307);
    expect(anonymous.headers.get("location")).toBe("http://localhost:3000/login");

    const signedIn = proxy(
      request("/applications/42", { access_token: liveToken() })
    );
    expect(isNext(signedIn)).toBe(true);
  });
});
