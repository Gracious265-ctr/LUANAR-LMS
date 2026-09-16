import { cookies } from "next/headers";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

export interface DjangoUser {
  id: number;
  email: string;
  role: string;
  full_name: string;
}

export interface DjangoTokens {
  access: string;
  refresh: string;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let response = await fetch(`${DJANGO_API_URL}${endpoint}`, {
    ...options,
    headers,
  });

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
        response = await fetch(`${DJANGO_API_URL}${endpoint}`, {
          ...options,
          headers,
        });
      }
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}
