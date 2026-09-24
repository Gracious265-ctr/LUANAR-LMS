import { proxyRequest } from "../../../leave/_lib/proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ requestId: string }> }
) {
  const { requestId } = await params;
  return proxyRequest(
    "GET",
    `approvals/cancellations/${encodeURIComponent(requestId)}/`
  );
}