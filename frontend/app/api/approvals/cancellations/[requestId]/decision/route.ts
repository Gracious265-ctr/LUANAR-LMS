import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
  const body = await request.json();
  return apiFetch("POST", `approvals/cancellations/${requestId}/decision/`, {
    body,
  });
}