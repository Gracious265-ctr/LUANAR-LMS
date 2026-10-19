import { NextRequest } from "next/server";

import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * `/api/leave-config/types/` — the leave-type registry (§4.4).
 *
 * The list is readable by every authenticated user (each module's dropdowns
 * need it) while only HR may create; `apiFetch` carries the bearer token and
 * Django's `IsLeaveConfigAccess` is what actually enforces the split.
 */
export async function GET(request: NextRequest) {
  const includeInactive =
    request.nextUrl.searchParams.get("include_inactive") === "true";
  const query = includeInactive ? "?include_inactive=true" : "";
  return apiFetch("GET", `leave-config/types/${query}`);
}

export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "leave-config/types/", { body });
}
