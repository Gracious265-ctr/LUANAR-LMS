import { proxyRequest } from "../../../../_lib/proxy";

/**
 * Reads one supporting document on demand. The documents feed lists rows
 * without a signed URL (signing is a storage round-trip per row), so opening a
 * row mints the single URL it needs through this endpoint.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  return proxyRequest("GET", `leave-applications/${id}/documents/${docId}/`);
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  return proxyRequest("DELETE", `leave-applications/${id}/documents/${docId}/`);
}
