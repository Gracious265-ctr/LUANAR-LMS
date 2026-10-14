/**
 * Client for the generated approved-leave document (Unit 23b).
 *
 * The document itself is never proxied through Next.js: the backend mints a
 * short-lived signed URL and the browser opens that directly, so a PDF of an
 * employee's leave approval is never buffered by this server.
 */

export type ApprovedDocumentStatus = "pending" | "ready" | "failed";

export interface ApprovedLeaveDocument {
  id: string;
  application: string;
  status: ApprovedDocumentStatus;
  available: boolean;
  file_name: string;
  content_type: string;
  file_size: number;
  approved_on: string | null;
  rendered_at: string | null;
  created_at: string;
  /** Empty while the document is not yet available. */
  download_url: string;
}

export type ApprovedDocumentResult =
  | { ok: true; data: ApprovedLeaveDocument }
  | { ok: false; kind: "not_found" | "error"; message?: string };

async function read(
  path: string
): Promise<ApprovedDocumentResult> {
  try {
    const res = await fetch(path, { credentials: "include" });
    if (res.status === 404) {
      return { ok: false, kind: "not_found" };
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message:
          (data as { error?: string }).error ||
          "Could not load the approved document.",
      };
    }
    return { ok: true, data: data as ApprovedLeaveDocument };
  } catch {
    return {
      ok: false,
      kind: "error",
      message: "Could not reach the server. Try again shortly.",
    };
  }
}

/** The document for an application, as its owner or an approver. */
export function fetchApprovedDocument(
  applicationId: string
): Promise<ApprovedDocumentResult> {
  return read(
    `/api/approved-leave-documents/by-application/${encodeURIComponent(applicationId)}/`
  );
}

/** The same document through the HR audit route. */
export function fetchHRAapprovedDocument(
  applicationId: string
): Promise<ApprovedDocumentResult> {
  return read(
    `/api/hr/approved-leave-documents/by-application/${encodeURIComponent(applicationId)}/`
  );
}
