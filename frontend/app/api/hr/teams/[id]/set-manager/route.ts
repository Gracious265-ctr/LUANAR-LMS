import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Designate the person who runs this team.
 *
 * HR-only on the backend. `user` alone is enough: the designation is the
 * team's `manager` field, so an institution-wide approver — who holds no
 * team-scoped role — can be named without inventing one.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  return apiFetch("POST", `teams/${id}/set-manager/`, { body });
}
