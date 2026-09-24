import { proxyRequest } from "../../../../leave/_lib/proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
  const body = await request.json().catch(() => ({}));
  return proxyRequest(
    "POST",
    `approvals/cancellations/${encodeURIComponent(requestId)}/decision/`,
    body
  );
}