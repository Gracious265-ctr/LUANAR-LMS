import { proxyRequest } from "../../../../_lib/proxy";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  return proxyRequest("DELETE", `leave-applications/${id}/documents/${docId}/`);
}
