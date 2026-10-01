import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

/**
 * Anonymous by design — the person asking has no password, and therefore no
 * session. Same shape as the login proxy: the Django URL stays server-side, and
 * the answer is passed through untouched so a person learns nothing about which
 * addresses have accounts.
 */
export async function POST(request: Request) {
  const body = await request.json();

  const response = await fetch(`${DJANGO_API_URL}/api/v1/auth/password-set/request/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Could not send the link." }));
    return NextResponse.json(error, { status: response.status });
  }

  return NextResponse.json(await response.json());
}
