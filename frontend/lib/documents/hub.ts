import { apiClientUrl } from "@/lib/api-client";
import type { BadgeTone } from "@/components/ui/badge";

/**
 * The read side of the Documents hub.
 *
 * Server-only: both lists are fetched during the page render with the request's
 * own cookie, so the hub never spends an extra round trip in the browser.
 * Whose documents come back is decided in Django by a single predicate
 * (`documents.access.visible_employee_ids`) — an employee reads their own, a
 * team manager also reads their teams', HR reads the institution — so nothing
 * here re-implements that scope. The frontend only shapes and formats it.
 *
 * The endpoint returns a plain array rather than a paginated envelope: the
 * scope is a person's own filing cabinet, or at most HR's whole institution of
 * ready documents, and the existing single-document endpoints are arrays too.
 */

/** The filing a document belongs to — the leave application behind it. */
export interface HubFiling {
  id: string;
  reference_number: string;
}

/** Whose document it is. */
export interface HubOwner {
  id: number;
  full_name: string;
}

export type SupportingDocumentState = "active" | "retired";

export type RetireReason = "replaced" | "removed" | (string & {});

export interface HubSupportingDocument {
  id: string;
  file_name: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
  status: SupportingDocumentState;
  retire_reason: RetireReason | null;
  retired_at: string | null;
  /** Signed where storage allows, the stored URL otherwise. */
  file_url: string;
  application: HubFiling;
  employee: HubOwner;
}

export type ApprovedDocumentState = "pending" | "ready" | "failed";

export interface HubApprovedDocument {
  id: string;
  status: ApprovedDocumentState;
  /** Whether `download_url` opens now; false while pending or failed. */
  available: boolean;
  file_name: string;
  content_type: string;
  file_size: number;
  approved_on: string | null;
  rendered_at: string | null;
  created_at: string;
  /** Signed at read time; empty while the document is not available. */
  download_url: string;
  application: HubFiling;
  employee: HubOwner;
}

/**
 * The viewer's supporting documents, newest filing first.
 *
 * Retired rows are held back by default so the list reads as "what is on file
 * now"; `includeRetired` surfaces the ones a later upload replaced.
 */
export async function listSupportingDocuments(
  options: { includeRetired?: boolean } = {}
): Promise<HubSupportingDocument[]> {
  const query = options.includeRetired ? "?include_retired=true" : "";
  return apiClientUrl<HubSupportingDocument[]>(
    `/api/v1/documents/supporting/${query}`
  );
}

/** The viewer's generated leave documents, newest first. */
export async function listApprovedDocuments(): Promise<HubApprovedDocument[]> {
  return apiClientUrl<HubApprovedDocument[]>("/api/v1/documents/approved/");
}

interface StateMeta {
  label: string;
  tone: BadgeTone;
}

/** Status pill for a filing that is on record. */
export const SUPPORTING_STATUS: Record<SupportingDocumentState, StateMeta> = {
  active: { label: "Active", tone: "approved" },
  retired: { label: "Retired", tone: "muted" },
};

/** Status pill for a generated document. */
export const APPROVED_STATUS: Record<ApprovedDocumentState, StateMeta> = {
  pending: { label: "Being prepared", tone: "pending" },
  ready: { label: "Ready", tone: "approved" },
  failed: { label: "Failed", tone: "rejected" },
};

/** Why a supporting document was taken off the filing. */
export const RETIRE_REASON_LABELS: Record<string, string> = {
  replaced: "Replaced by a newer upload",
  removed: "Removed",
};

export function retireReasonLabel(reason: RetireReason | null): string {
  if (!reason) return "";
  return RETIRE_REASON_LABELS[reason] ?? reason;
}

/** Human file size, e.g. "1.4 MB". */
export function formatFileSize(bytes: number): string {
  if (!bytes || bytes < 1) return "";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes;
  let unit = "B";
  for (const next of units) {
    if (value < 1024) break;
    value /= 1024;
    unit = next;
  }
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)} ${unit}`;
}
