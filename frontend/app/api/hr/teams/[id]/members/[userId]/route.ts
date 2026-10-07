import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Take one employee off this team.
 *
 * A 409 names every responsibility that still ties the person to the team
 * (a step appointment, an open approver period, a normal workflow membership,
 * a team-wide holding), which is what HR needs before they can release the
 * person one at a time.
 */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; userId: string }> }
) {
  const { id, userId } = await params;
  return apiFetch("DELETE", `teams/${id}/members/${userId}/`);
}