import { proxyRequest } from "../../../leave/_lib/proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json().catch(() => ({}));
  return proxyRequest(
    "POST",
    `applications/${encodeURIComponent(id)}/resubmit/`,
    body
  );
}