import { apiFetch } from "@/app/api/_lib/api-fetch";

<<<<<<< HEAD
=======
/**
 * Who may be added to this team's roster.
 *
 * The team members picker reads this rather than the employee directory: the
 * directory is an HR read, and the backend's candidate list is already scoped
 * to exactly who the add would accept (unassigned, category-matched, not a wide
 * approver), so a manager sees their own team's candidates and no other's.
 */
>>>>>>> features/team-base
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("GET", `teams/${id}/member-candidates/`);
}
