export interface SupportingDocument {
  id: string;
  file_path: string;
  file_url: string;
  file_name: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
}

export interface LeaveApplication {
  id: string;
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  calculated_days: number | null;
  reason: string;
  status: "draft" | "submitted";
  reference_number: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  documents: SupportingDocument[];
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

export async function submitLeaveApplication(
  id: string
): Promise<{ detail: string; reference_number: string }> {
  const res = await fetch(`/api/leave/leave-applications/${id}/submit/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to submit" }));
    throw new Error(error.detail || "Failed to submit application");
  }
  return res.json();
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
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to upload" }));
    throw new Error(error.detail || "Failed to upload document");
  }
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
  if (!res.ok) throw new Error("Failed to delete document");
}
