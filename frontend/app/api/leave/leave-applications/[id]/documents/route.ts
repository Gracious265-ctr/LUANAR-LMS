import { proxyRequest } from "../../../_lib/proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRequest("GET", `leave-applications/${id}/documents/`);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const formData = await request.formData();
  return proxyRequest("POST", `leave-applications/${id}/documents/`, formData, true);
}
