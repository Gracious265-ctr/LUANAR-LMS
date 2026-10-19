/**
 * Client for the documents module's two owner-scoped feeds: the supporting
 * documents attached to the caller's leave applications, and their generated
 * approved leave documents.
 *
 * Both endpoints are paginated lists; each row carries enough context (the
 * parent application's reference) to name and link back to the application it
 * belongs to. Neither feed carries a file URL: minting one is a storage
 * round-trip per row, which made the list slow. The URL is minted only when a
 * row is opened — see `fetchSupportingDocumentUrl` and `fetchApprovedDocumentUrl`.
 */

import { fetchApprovedDocument } from "@/lib/documents/approved";

export interface SupportingDocumentFeedRow {
  id: string;
  /** Always empty in the feed; the URL is fetched on demand. */
  file_url: string;
  file_name: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
  status: "active" | "retired";
  retired_at: string | null;
  retire_reason: "replaced" | "removed" | null;
  retired_by: { id: number; name: string } | null;
  replaced_by: { id: string; file_name: string } | null;
  application: {
    id: string;
    reference_number: string | null;
    status: string;
  };
}

export type ApprovedDocumentStatus = "pending" | "ready" | "failed";

export interface ApprovedDocumentFeedRow {
  id: string;
  application: string;
  reference_number: string | null;
  status: ApprovedDocumentStatus;
  /** True when a ready document exists, so the row can offer to open it. */
  available: boolean;
  file_name: string;
  content_type: string;
  file_size: number;
  approved_on: string | null;
  rendered_at: string | null;
  created_at: string;
  /** Always empty in the feed; the URL is fetched on demand. */
  download_url: string;
}

export interface FeedPage<T> {
  count: number;
  results: T[];
}

async function fetchFeed<T>(url: string): Promise<FeedPage<T>> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error("Could not load your documents. Please try again.");
  }
  const body = (await res.json().catch(() => ({}))) as Partial<FeedPage<T>>;
  return { count: body.count ?? 0, results: body.results ?? [] };
}

/** Supporting documents attached to any of the caller's applications. */
export function listMySupportingDocuments(
  { includeRetired = false }: { includeRetired?: boolean } = {}
): Promise<FeedPage<SupportingDocumentFeedRow>> {
  const url = includeRetired
    ? "/api/leave-documents/?include_retired=true"
    : "/api/leave-documents/";
  return fetchFeed<SupportingDocumentFeedRow>(url);
}

/** Generated approved leave documents for the caller's applications. */
export function listMyApprovedDocuments(): Promise<
  FeedPage<ApprovedDocumentFeedRow>
> {
  return fetchFeed<ApprovedDocumentFeedRow>("/api/approved-leave-documents/");
}

/**
 * The signed URL for one supporting document, minted when the row is opened.
 * The per-document endpoint is owner-scoped, so this cannot fetch another
 * employee's file.
 */
export async function fetchSupportingDocumentUrl(
  applicationId: string,
  documentId: string
): Promise<string> {
  const res = await fetch(
    `/api/leave/leave-applications/${encodeURIComponent(
      applicationId
    )}/documents/${encodeURIComponent(documentId)}/`,
    { credentials: "include" }
  );
  if (!res.ok) {
    throw new Error("Could not prepare the document. Please try again.");
  }
  const body = (await res.json().catch(() => ({}))) as { file_url?: string };
  return body.file_url ?? "";
}

/** The signed download URL for an application's approved document. */
export async function fetchApprovedDocumentUrl(
  applicationId: string
): Promise<string> {
  const result = await fetchApprovedDocument(applicationId);
  if (!result.ok || !result.data.download_url) {
    throw new Error("Could not prepare the document. Please try again.");
  }
  return result.data.download_url;
}
