import { proxyRequest } from "../../../../../../leave/_lib/proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; documentId: string }> }
) {
  const { id, documentId } = await params;
  const formData = await request.formData();
  return proxyRequest(
    "POST",
    `applications/${encodeURIComponent(id)}/resubmission/documents/${encodeURIComponent(documentId)}/replace/`,
    formData,
    true
  );
}