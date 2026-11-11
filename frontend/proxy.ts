import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const protectedRoutes = ["/dashboard", "/applications"];
const authRoutes = ["/login"];

/**
 * The `exp` claim of a JWT, without verifying its signature.
 *
 * The proxy runs before Django and only decides where a browser should be sent.
 * It must not pretend to authorise anything: the signature check stays in the
 * API, which answers 401 for a token the proxy waved through. Reading `exp`
 * here is what stops a stale cookie from being mistaken for a live session —
 * and, crucially, lets a valid refresh token keep the session alive after the
 * 15-minute access cookie has expired.
 *
 * Returns `null` for a missing or malformed payload. Callers treat that as
 * "not live", which sends the request towards the login page rather than
 * trusting a token nobody can parse.
 */
function tokenExpiry(token: string | undefined): number | null {
  if (!token) return null;
  const payload = token.split(".")[1];
  if (!payload) return null;

  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const claims = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof claims.exp === "number" ? claims.exp : null;
  } catch {
    return null;
  }
}

function isLive(token: string | undefined, nowSeconds: number): boolean {
  const expiry = tokenExpiry(token);
  return expiry !== null && expiry > nowSeconds;
}

function hasLiveSession(request: NextRequest): boolean {
  const nowSeconds = Math.floor(Date.now() / 1000);
  // Either token is enough. The access token is short-lived by design, so
  // requiring it here would end a valid one-day session every 15 minutes; the
  // refresh token is the one that actually represents the session.
  return (
    isLive(request.cookies.get("access_token")?.value, nowSeconds) ||
    isLive(request.cookies.get("refresh_token")?.value, nowSeconds)
  );
}

/**
 * Send the browser to the login page and forget the dead cookies.
 *
 * Clearing them matters as much as the redirect: the browser showed up with
 * cookies that cannot produce a session, and leaving them in place is how an
 * expired access cookie used to bounce `/dashboard` → `/login` → `/` and back
 * forever, because the login route saw "a token" and considered the user
 * signed in.
 */
function redirectToLogin(request: NextRequest): NextResponse {
  const response = NextResponse.redirect(new URL("/login", request.url));
  response.cookies.delete("access_token");
  response.cookies.delete("refresh_token");
  return response;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtectedRoute = protectedRoutes.some((route) =>
    pathname.startsWith(route)
  );
  const isAuthRoute = authRoutes.some((route) => pathname.startsWith(route));
  const signedIn = hasLiveSession(request);

  if (isProtectedRoute && !signedIn) {
    return redirectToLogin(request);
  }

  if (isAuthRoute && signedIn) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Route groups do not appear in the URL, so `/applications/[id]` lives under
  // `app/(dashboard)` but resolves outside `/dashboard`. It is guarded by the
  // group's layout too, but matching it here means a signed-out visitor is
  // redirected before any render and their dead cookies are cleared instead of
  // lingering. `/api/**` and static assets are deliberately unmatched.
  matcher: ["/dashboard/:path*", "/applications/:path*", "/login/:path*"],
};
