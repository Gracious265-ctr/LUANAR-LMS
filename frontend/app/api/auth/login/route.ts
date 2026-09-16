import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

export async function POST(request: Request) {
  const body = await request.json();

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
