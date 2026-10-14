<<<<<<< HEAD
import { proxyRequest } from "../../../leave/_lib/proxy";
=======
import { apiFetch } from "@/app/api/_lib/api-fetch";
>>>>>>> feature/plans-teams

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
<<<<<<< HEAD
  return proxyRequest(
    "GET",
    `approvals/cancellations/${encodeURIComponent(requestId)}/`
  );
=======
  return apiFetch("GET", `approvals/cancellations/${requestId}/`);
>>>>>>> feature/plans-teams
}