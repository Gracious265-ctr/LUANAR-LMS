import { cookies } from "next/headers";

import { apiClient, type DjangoUser } from "./api-client";

export async function getCurrentUser(): Promise<DjangoUser | null> {
  try {
    const user = await apiClient<DjangoUser>("/api/v1/auth/me/");
    return user;
  } catch {
    return null;
  }
}

export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  return !!cookieStore.get("access_token")?.value;
}
