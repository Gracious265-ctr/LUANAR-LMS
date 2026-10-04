"use client";

import type { LeaveType, LeaveTypeListResponse } from "./leave-rules";

export async function listLeaveTypes(): Promise<LeaveTypeListResponse> {
  const response = await fetch("/api/hr/leave-types", { method: "GET" });
  if (!response.ok) {
    throw new Error("Failed to load leave types");
  }
  return response.json();
}

export async function getLeaveType(id: number | string): Promise<LeaveType> {
  const response = await fetch(`/api/hr/leave-types/${id}`);
  if (!response.ok) {
    throw new Error("Failed to load leave type");
  }
  return response.json();
}
