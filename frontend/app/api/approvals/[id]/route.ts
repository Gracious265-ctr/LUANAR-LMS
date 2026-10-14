<<<<<<< HEAD
import { proxyRequest } from "../../leave/_lib/proxy";
=======
import { apiFetch } from "@/app/api/_lib/api-fetch";
>>>>>>> feature/plans-teams

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
<<<<<<< HEAD
  return proxyRequest("GET", `approvals/${encodeURIComponent(id)}/`);
=======
  return apiFetch("GET", `approvals/${id}/`);
>>>>>>> feature/plans-teams
}