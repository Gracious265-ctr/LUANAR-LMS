import { apiFetch } from "@/app/api/_lib/api-fetch";

/**
 * Remove this team's manager, whether designated on the team or through a
 * team-wide holding. HR-only on the backend; the team keeps its roster and its
 * chains.
 */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return apiFetch("POST", `teams/${id}/clear-manager/`);
}
