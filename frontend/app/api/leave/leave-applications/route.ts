import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

async function proxyRequest(
  method: string,
  path: string,
  body?: unknown,
  isFormData = false
) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  if (!isFormData && body) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${DJANGO_API_URL}/api/v1/${path}`, {
    method,
    headers,
    body: isFormData ? (body as FormData) : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function GET() {
  return proxyRequest("GET", "leave-applications/");
}

export async function POST(request: Request) {
  const body = await request.json();
  return proxyRequest("POST", "leave-applications/", body);
}
