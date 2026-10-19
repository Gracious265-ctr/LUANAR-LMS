import { redirect } from "next/navigation";

import { apiClient, type DjangoUser } from "./api-client";
import { getCurrentUser } from "./auth";
import type { LeaveType } from "./leave-config";

/**
 * Server-side reads of the leave-type registry, plus the page's access gate.
 *
 * This module imports `api-client`, which reads the JWT cookie, so it is
 * server-only. The pure shapes and helpers live in `lib/leave-config.ts` and
 * the browser-side writes in `lib/leave-config-client.ts`; keeping the three
 * apart is what lets a client component use the vocabulary without pulling
 * `next/headers` into the client bundle.
 */

/**
 * Mirror of `leave_config.services.can_access_leave_config` (§4.3 / A1).
 *
 * Only `is_superuser` and `role` come back on the serialized user, so this is
 * the same rule the launcher's card and the Django gate apply in the two arms
 * the client can actually see. `is_staff` — the backend's third arm — is not
 * serialized, exactly as it is missing from the shell's `showHR`/`showAdmin`
 * mirrors; accounts in that gap are created by `createsuperuser`, which sets
 * `is_superuser` too.
 */
export function canAccessLeaveConfig(user: DjangoUser | null): boolean {
  if (!user) return false;
  if (user.is_superuser === true) return true;
  return user.role === "hr";
}

/**
 * The gate every `/leave-config` page calls first: no user to the login page,
 * and anyone the launcher would not show the card to back to their dashboard.
 * Django still refuses the writes (§4.4) — this only keeps HR's screens out of
 * a URL a non-HR account guessed.
 */
export async function requireLeaveConfigAccess(): Promise<DjangoUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }
  if (!canAccessLeaveConfig(user)) {
    redirect("/dashboard");
  }
  return user;
}

/**
 * The registry as the HR screens see it.
 *
 * Retired types are hidden unless asked for (§3.2's "Show inactive"); other
 * modules' dropdowns rely on that default so a deactivated type stops being
 * offered without every caller having to remember to filter it.
 */
export async function listLeaveTypes(
  options: { includeInactive?: boolean } = {}
): Promise<LeaveType[]> {
  const query = options.includeInactive ? "?include_inactive=true" : "";
  return apiClient<LeaveType[]>(`/api/v1/leave-config/types/${query}`);
}

export async function getLeaveType(id: string): Promise<LeaveType> {
  return apiClient<LeaveType>(`/api/v1/leave-config/types/${id}/`);
}
