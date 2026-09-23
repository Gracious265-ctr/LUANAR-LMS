import { proxyRequest } from "../../../leave/_lib/proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRequest(
    "GET",
    `applications/${encodeURIComponent(id)}/resubmission/`
  );
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json().catch(() => ({}));
  return proxyRequest(
    "PATCH",
    `applications/${encodeURIComponent(id)}/resubmission/`,
    body
  );
}