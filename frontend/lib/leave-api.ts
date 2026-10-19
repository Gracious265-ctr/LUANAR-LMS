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

const DOCUMENT_ERRORS: Record<string, string> = {
  application_not_editable:
    "This application is no longer editable. Documents can only be changed on a draft or while it is rejected.",
  document_not_active:
    "This document has already been removed or replaced.",
};

async function documentError(res: Response, fallback: string): Promise<Error> {
  const body = await res.json().catch(() => ({}));
  const detail =
    (body?.detail as string | undefined) ||
    DOCUMENT_ERRORS[body?.code as string] ||
    fallback;
  return new Error(detail);
}

export async function getLeaveApplications(status?: string): Promise<{
  count: number;
  results: LeaveApplication[];
}> {
  const url = new URL("/api/leave/leave-applications/", window.location.origin);
  if (status) url.searchParams.set("status", status);
  const res = await fetch(url.toString(), {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch applications");
  return res.json();
}

export async function getLeaveApplication(
  id: string
): Promise<LeaveApplication> {
  const res = await fetch(`/api/leave/leave-applications/${id}/`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch application");
  return res.json();
}

export async function createLeaveApplication(
  data: Partial<LeaveApplication>
): Promise<LeaveApplication> {
  const res = await fetch("/api/leave/leave-applications/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create" }));
    throw new Error(error.detail || "Failed to create application");
  }
  return res.json();
}

export async function updateLeaveApplication(
  id: string,
  data: Partial<LeaveApplication>
): Promise<LeaveApplication> {
  const res = await fetch(`/api/leave/leave-applications/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to update" }));
    throw new Error(error.detail || "Failed to update application");
  }
  return res.json();
}

export async function deleteLeaveApplication(id: string): Promise<void> {
  const res = await fetch(`/api/leave/leave-applications/${id}/`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete application");
}

export async function uploadDocument(
  applicationId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(
    `/api/leave/leave-applications/${applicationId}/documents/`,
    {
      method: "POST",
      credentials: "include",
      body: formData,
    }
  );
  if (!res.ok) throw await documentError(res, "Failed to upload document");
  return res.json();
}

export async function listDocuments(
  applicationId: string,
  { includeRetired = false }: { includeRetired?: boolean } = {}
): Promise<SupportingDocument[]> {
  const res = await fetch(
    `/api/leave/leave-applications/${applicationId}/documents/${
      includeRetired ? "?include_retired=true" : ""
    }`,
    { credentials: "include" }
  );
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function deleteDocument(
  applicationId: string,
  documentId: string
): Promise<void> {
  const res = await fetch(
    `/api/leave/leave-applications/${applicationId}/documents/${documentId}/`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );
  if (!res.ok) throw await documentError(res, "Failed to delete document");
}

export async function replaceDocument(
  applicationId: string,
  documentId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(
    `/api/leave/leave-applications/${applicationId}/documents/${documentId}/replace/`,
    {
      method: "POST",
      credentials: "include",
      body: formData,
    }
  );
  if (!res.ok) throw await documentError(res, "Failed to replace document");
  const data = await res.json();
  return data.document;
}
