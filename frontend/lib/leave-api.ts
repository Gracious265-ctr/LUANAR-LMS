import { apiErrorMessage } from "./utils";

export interface SupportingDocument {
  id: string;
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
}

export interface LeaveApplication {
  id: string;
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  calculated_days: number | null;
  reason: string;
  status:
    | "draft"
    | "submitted"
    | "approved"
    | "rejected"
    | "cancelled";
  reference_number: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  working_days: number | null;
  calendar_days: number | null;
  financial_year_label: string | null;
  documents: SupportingDocument[];
}

/**
 * Machine-readable document errors the API returns in place of a `detail`
 * sentence. Kept as a code→message map because these two refuse a document
 * write for a reason no prose `detail` carries, and the client shows the
 * sentence itself rather than a generic banner.
 */
const DOCUMENT_ERRORS: Record<string, string> = {
  application_not_editable:
    "This application is no longer editable. Documents can only be changed on a draft or while it is rejected.",
  document_not_active:
    "This document has already been removed or replaced.",
};

/**
 * The single seam every call in this module goes through.
 *
 * Parses the DRF error body the same way the rest of the leave client does
 * (``apiErrorMessage`` reads ``detail``, then the first message of each field),
 * and folds in the code-keyed document errors above so a refusal without a
 * sentence still reads as one. A non-JSON or empty body falls back to the
 * caller's generic message — the one thing a caller knows that the body does
 * not: what it was trying to do.
 */
async function request<T>(
  path: string,
  { fallback, ...init }: RequestInit & { fallback: string }
): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const code =
      body && typeof body === "object"
        ? (body as { code?: string }).code
        : undefined;
    const hasBody =
      body != null &&
      (typeof body !== "object" || Object.keys(body as object).length > 0);
    const message =
      (code && DOCUMENT_ERRORS[code]) ||
      (hasBody ? apiErrorMessage(body) : "") ||
      fallback;
    throw new Error(message);
  }
  // A 204 (DELETE) has no body; a caller that returns ``void`` expects nothing
  // back, and parsing an empty stream would throw where the request succeeded.
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

const API = "/api/leave/leave-applications";

export async function getLeaveApplications(
  {
    status,
    excludeStatus,
  }: { status?: string; excludeStatus?: string } = {}
): Promise<{
  count: number;
  results: LeaveApplication[];
}> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (excludeStatus) params.set("exclude_status", excludeStatus);
  const query = params.toString();
  return request(
    `/api/leave/leave-applications/${query ? `?${query}` : ""}`,
    {
    credentials: "include",
    fallback: "Failed to fetch applications",
  });
}

export async function getLeaveApplication(
  id: string
): Promise<LeaveApplication> {
  return request(`${API}/${id}/`, {
    credentials: "include",
    fallback: "Failed to fetch application",
  });
}

export async function createLeaveApplication(
  data: Partial<LeaveApplication>
): Promise<LeaveApplication> {
  return request(`${API}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
    fallback: "Failed to create application",
  });
}

export async function updateLeaveApplication(
  id: string,
  data: Partial<LeaveApplication>
): Promise<LeaveApplication> {
  return request(`${API}/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
    fallback: "Failed to update application",
  });
}

export async function deleteLeaveApplication(id: string): Promise<void> {
  await request(`${API}/${id}/`, {
    method: "DELETE",
    credentials: "include",
    fallback: "Failed to delete application",
  });
}

export async function uploadDocument(
  applicationId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  return request(`${API}/${applicationId}/documents/`, {
    method: "POST",
    credentials: "include",
    body: formData,
    fallback: "Failed to upload document",
  });
}

export async function listDocuments(
  applicationId: string,
  { includeRetired = false }: { includeRetired?: boolean } = {}
): Promise<SupportingDocument[]> {
  return request(
    `${API}/${applicationId}/documents/${
      includeRetired ? "?include_retired=true" : ""
    }`,
    { credentials: "include", fallback: "Failed to fetch documents" }
  );
}

export async function deleteDocument(
  applicationId: string,
  documentId: string
): Promise<void> {
  await request(`${API}/${applicationId}/documents/${documentId}/`, {
    method: "DELETE",
    credentials: "include",
    fallback: "Failed to delete document",
  });
}

export async function replaceDocument(
  applicationId: string,
  documentId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const data = await request<{ document: SupportingDocument }>(
    `${API}/${applicationId}/documents/${documentId}/replace/`,
    {
      method: "POST",
      credentials: "include",
      body: formData,
      fallback: "Failed to replace document",
    }
  );
  return data.document;
}
