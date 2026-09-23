import { proxyRequest } from "../../../../../leave/_lib/proxy";

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string; documentId: string }> }
) {
  const { id, documentId } = await params;
  const body = await request.json().catch(() => ({}));
  return proxyRequest(
    "DELETE",
    `applications/${encodeURIComponent(id)}/resubmission/documents/${encodeURIComponent(documentId)}/`,
    body
  );
}