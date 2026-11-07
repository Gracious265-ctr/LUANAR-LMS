import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

/**
 * Sign out on both sides.
 *
 * Clearing the httpOnly cookies is only half of it: the refresh token is a
 * bearer credential, and until Django blacklists it a copy of the cookie keeps
 * minting access tokens for the rest of its 24-hour life. The refresh token is
 * sent to the logout endpoint first, then both cookies are cleared whatever the
 * upstream answer was — a user who clicks "Sign out" must end up signed out even
 * if Django is unreachable.
 */
export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (refreshToken) {
    try {
      await fetch(`${DJANGO_API_URL}/api/v1/auth/logout/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
        cache: "no-store",
      });
    } catch {
      // Best effort. The cookies are cleared below either way, and the token
      // expires on its own if the revocation could not be delivered.
    }
  }

  const nextResponse = NextResponse.json({ success: true });

  nextResponse.cookies.set("access_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  nextResponse.cookies.set("refresh_token", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  return nextResponse;
}
