import { proxyRequest } from "../../../../leave/_lib/proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const formData = await request.formData();
  return proxyRequest(
    "POST",
    `applications/${encodeURIComponent(id)}/resubmission/documents/`,
    formData,
    true
  );
}