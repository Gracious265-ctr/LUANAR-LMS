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

async function authorizedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let response = await fetch(url, { ...options, headers });

  if (response.status === 401 && accessToken) {
    const refreshToken = cookieStore.get("refresh_token")?.value;
    if (refreshToken) {
      const refreshResponse = await fetch(
        `${DJANGO_API_URL}/api/v1/auth/refresh/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        }
      );

      if (refreshResponse.ok) {
        const { access: newAccess } = await refreshResponse.json();
        headers["Authorization"] = `Bearer ${newAccess}`;
        response = await fetch(url, { ...options, headers });
      }
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
