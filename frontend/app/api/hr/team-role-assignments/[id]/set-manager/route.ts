import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Designate a team-wide holding as its team's manager.
 *
 * HR-only, like every write under team-role-assignments: the backend holds the
 * rule and refuses a manager's token, so this route is a plain pass-through.
 */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("POST", `team-role-assignments/${id}/set-manager/`);
}
