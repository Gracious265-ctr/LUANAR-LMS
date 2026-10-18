import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * The routing decision is the manager's alone, so it is a dedicated write
 * rather than a field on the team update the form sends: the backend refuses a
 * chain the team does not own, and this proxy keeps the browser unable to ask
 * for anything the route action itself would refuse.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("POST", `teams/${id}/route/`, { body });
}