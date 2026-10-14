<<<<<<< HEAD
import { proxyRequest } from "../../../../leave/_lib/proxy";
=======
import { apiFetch } from "@/app/api/_lib/api-fetch";
>>>>>>> feature/plans-teams

export async function POST(
  request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
<<<<<<< HEAD
  const body = await request.json().catch(() => ({}));
  return proxyRequest(
    "POST",
    `approvals/cancellations/${encodeURIComponent(requestId)}/decision/`,
    body
  );
=======
  const body = await request.json();
  return apiFetch("POST", `approvals/cancellations/${requestId}/decision/`, {
    body,
  });
>>>>>>> feature/plans-teams
}