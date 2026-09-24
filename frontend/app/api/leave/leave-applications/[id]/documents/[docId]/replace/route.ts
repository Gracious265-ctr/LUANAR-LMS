import { proxyRequest } from "../../../../../_lib/proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  const formData = await request.formData();
  return proxyRequest(
    "POST",
    `leave-applications/${id}/documents/${docId}/replace/`,
    formData,
    true
  );
}