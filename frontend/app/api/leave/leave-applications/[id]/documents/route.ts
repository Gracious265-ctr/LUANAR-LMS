import { proxyRequest } from "../../../_lib/proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const includeRetired = new URL(request.url).searchParams.get(
    "include_retired"
  );
  const path = includeRetired
    ? `leave-applications/${id}/documents/?include_retired=true`
    : `leave-applications/${id}/documents/`;
  return proxyRequest("GET", path);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const formData = await request.formData();
  return proxyRequest("POST", `leave-applications/${id}/documents/`, formData, true);
}