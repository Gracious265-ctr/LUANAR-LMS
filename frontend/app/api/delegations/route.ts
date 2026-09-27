import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Create a delegation request.
 *
 * Not namespaced under /api/hr because the common caller is the approver
 * themselves. The Django viewset is the only thing that decides whether this
 * is a self-service request or HR acting on someone's behalf.
 */
export async function POST(request: Request) {
  const body = await request.json();
  return apiFetch("POST", "delegations/", { body });
}
