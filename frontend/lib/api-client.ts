import { cookies } from "next/headers";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

export interface DjangoUser {
  id: number;
  email: string;
  role: string;
  full_name: string;
  /**
   * The bootstrap administrator. Read-only and server-assigned: it is the
   * account created with `createsuperuser`, and it is what unlocks the
   * admin user-management area. Absent on responses from older clients/tests
   * that predate the field, so callers treat it as optional.
   */
  is_superuser?: boolean;
  /**
   * The designated manager of at least one team. Read-only and server-derived,
   * and not implied by `role`: a manager is usually an ordinary employee, so
   * this is the only thing that tells the rail to offer them the Workflows
   * module. Optional for the same reason as `is_superuser`.
   */
  manages_teams?: boolean;
}

export interface DjangoTokens {
  access: string;
  refresh: string;
}

async function refreshAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;
  if (!refreshToken) return null;

  const response = await fetch(`${DJANGO_API_URL}/api/v1/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) return null;

  const data = await response.json().catch(() => null);
  return data?.access ?? null;
}

async function authorizedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;
  let accessToken = cookieStore.get("access_token")?.value;
  let triedRefresh = false;

  // The access cookie itself expires after 15 minutes while the refresh cookie
  // lasts a day. Without this branch, every render after that point went out
  // unauthenticated, got a 401, and — because the retry below only ran when an
  // access token was present — sent the signed-in user back to the login screen
  // even though their session was still valid. Refresh first so the request is
  // authenticated on its first attempt.
  if (!accessToken && refreshToken) {
    triedRefresh = true;
    accessToken = (await refreshAccessToken()) ?? undefined;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let response = await fetch(url, { ...options, headers });

  // A 401 means the token Django saw was expired (or invalid). Retry once with
  // a fresh one, whether the token came from the cookie or was just minted
  // above, so a clock skew or a token revoked mid-render is recovered without
  // bouncing the user out. If the refresh was already attempted before this
  // request, it failed: a second attempt would only repeat the same upstream
  // call.
  if (response.status === 401 && refreshToken && !triedRefresh) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${refreshed}`;
      response = await fetch(url, { ...options, headers });
    }
  }

  return response;
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }
  return response.json();
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  return unwrap<T>(await authorizedFetch(`${DJANGO_API_URL}${endpoint}`, options));
}

/**
 * Fetch a Django URL that may be relative or absolute.
 *
 * Absolute is needed to follow a paginated list's `next` link, which DRF
 * returns in full. Read as a whole rather than a page, because a picker built
 * from a truncated page silently offers fewer options than the backend has.
 */
export async function apiClientUrl<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const absolute = /^https?:\/\//.test(url) ? url : `${DJANGO_API_URL}${url}`;
  return unwrap<T>(await authorizedFetch(absolute, options));
}
