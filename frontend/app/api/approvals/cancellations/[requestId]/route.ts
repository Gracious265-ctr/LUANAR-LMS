import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
  return apiFetch("GET", `approvals/cancellations/${requestId}/`);
}