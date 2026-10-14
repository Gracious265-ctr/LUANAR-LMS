import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const token = url.searchParams.get("token");

  const response = await fetch(
    `${DJANGO_API_URL}/api/v1/auth/password-set/validate/?token=${encodeURIComponent(
      token ?? ""
    )}`,
    { cache: "no-store" }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Invalid link." }));
    return NextResponse.json(error, { status: response.status });
  }

  return NextResponse.json(await response.json());
}
