import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (!refreshToken) {
    return NextResponse.json(
      { detail: "No refresh token" },
      { status: 401 }
    );
  }

  const response = await fetch(`${DJANGO_API_URL}/api/v1/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Refresh failed" }));
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

  return nextResponse;
}
