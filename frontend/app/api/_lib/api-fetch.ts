import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

const ACCESS_TOKEN_COOKIE = "access_token";
const REFRESH_TOKEN_COOKIE = "refresh_token";
const ACCESS_TOKEN_MAX_AGE = 15 * 60;

interface ApiFetchOptions {
  body?: unknown;
  isFormData?: boolean;
}

async function refreshAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) return null;

  const res = await fetch(`${DJANGO_API_URL}/api/v1/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
    cache: "no-store",
  });
  if (!res.ok) return null;

  const data = await res.json().catch(() => null);
  return data?.access ?? null;
}

function buildRequest(
  method: string,
  path: string,
  options: ApiFetchOptions,
  accessToken: string
) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };
  if (options.body && !options.isFormData) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(`${DJANGO_API_URL}/api/v1/${path}`, {
    method,
    headers,
    body: options.isFormData
      ? (options.body as FormData)
      : options.body
        ? JSON.stringify(options.body)
        : undefined,
    cache: "no-store",
  });
}

export type ApiFetchResponse = NextResponse;

export async function apiFetch(
  method: string,
  path: string,
  options: ApiFetchOptions = {}
): Promise<NextResponse> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  let accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  let fresh: string | null = null;

  if (!accessToken && refreshToken) {
    accessToken = (await refreshAccessToken()) ?? undefined;
    if (accessToken) fresh = accessToken;
  }

  if (!accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let response = await buildRequest(method, path, options, accessToken);

  if (response.status === 401 && refreshToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      fresh = refreshed;
      response = await buildRequest(method, path, options, refreshed);
    }
  }

  let result: NextResponse;
  if (response.status === 204) {
    result = new NextResponse(null, { status: 204 });
  } else {
    const data = await response.json().catch(() => ({}));
    result = NextResponse.json(data, { status: response.status });
  }

  if (fresh) {
    result.cookies.set(ACCESS_TOKEN_COOKIE, fresh, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: ACCESS_TOKEN_MAX_AGE,
    });
  }

  return result;
}