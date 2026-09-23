import { proxyRequest } from "../../leave/_lib/proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRequest("GET", `approvals/${encodeURIComponent(id)}/`);
}