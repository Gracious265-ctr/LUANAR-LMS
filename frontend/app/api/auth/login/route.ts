import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

/**
 * Refuse a browser request that came from another site.
 *
 * Sign-in sets the session cookies, and it does so without needing any cookie of
 * its own — so `SameSite` cannot protect it. An attacker can host a page that
 * silently POSTs their own credentials here: the victim's browser accepts the
 * `Set-Cookie` response and from then on the victim works inside the attacker's
 * account, typing leave applications the attacker can later read (login CSRF).
 *
 * Checking `Origin` against `Host` is the standard defence and costs nothing.
 * A request with no `Origin` is not a browser form/fetch, and cannot cause a
 * browser to store a cookie, so it is allowed through — that keeps `curl`,
 * health checks, and any server-to-server caller working.
 */
function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;

  const host = request.headers.get("host");
  if (!host) return false;

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin sign-in is not allowed." }, {
      status: 403,
    });
  }

  const body = await request.json().catch(() => null);
  if (body === null) {
    return NextResponse.json({ detail: "Login failed" }, { status: 400 });
  }

  const response = await fetch(`${DJANGO_API_URL}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json(error, { status: response.status });
  }

  const data = await response.json();

  const nextResponse = NextResponse.json({ success: true });

  nextResponse.cookies.set("access_token", data.access, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 15 * 60, // 15 minutes
  });

  nextResponse.cookies.set("refresh_token", data.refresh, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24, // 1 day
  });

  return nextResponse;
}
