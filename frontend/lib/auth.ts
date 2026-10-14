import { cache } from "react";
import { cookies } from "next/headers";

import { apiClient, type DjangoUser } from "./api-client";

/**
 * The signed-in user, read once per request.
 *
 * The dashboard layout and every page beneath it each want this, and without
 * memoisation each call was a separate round trip to Django on the critical
 * path of the same render. `cache` scopes the read to one request, so N callers
 * cost one fetch — and it stays per-request, so one user's answer can never be
 * served to another.
 */
export const getCurrentUser = cache(async (): Promise<DjangoUser | null> => {
  try {
    const user = await apiClient<DjangoUser>("/api/v1/auth/me/");
    return user;
  } catch {
    return null;
  }
});

export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  return !!cookieStore.get("access_token")?.value;
}
