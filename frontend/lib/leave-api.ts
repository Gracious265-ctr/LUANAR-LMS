import type { SupportingDocument } from "@/lib/documents/types";

export type { SupportingDocument } from "@/lib/documents/types";

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
  working_days: number | null;
  calendar_days: number | null;
  financial_year_label: string | null;
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
