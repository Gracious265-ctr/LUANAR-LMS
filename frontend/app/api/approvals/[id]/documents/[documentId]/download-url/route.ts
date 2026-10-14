<<<<<<< HEAD
import { proxyRequest } from "../../../../../leave/_lib/proxy";

export async function GET(
  _request: Request,
  {
    params,
  }: { params: Promise<{ id: string; documentId: string }> }
) {
  const { id, documentId } = await params;
  return proxyRequest(
    "GET",
    `approvals/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/download-url/`
=======
import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; documentId: string }> }
) {
  const { id, documentId } = await params;
  return apiFetch(
    "GET",
    `approvals/${id}/documents/${documentId}/download-url/`
>>>>>>> feature/plans-teams
  );
}