export interface LeaveType {
  id: number;
  code: string;
  name: string;
  requiresDocuments: boolean;
  maxDurationDays: number | null;
}

interface BackendLeaveType {
  id: number;
  code: string;
  name: string;
  requires_supporting_document: boolean;
  max_duration_days: number | null;
}

export async function getLeaveTypes(): Promise<LeaveType[]> {
  const res = await fetch("/api/leave/leave-types/", {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch leave types");
  const items: BackendLeaveType[] = await res.json();
  return items.map((item) => ({
    id: item.id,
    name: item.name,
    code: item.code,
    requiresDocuments: item.requires_supporting_document,
    maxDurationDays: item.max_duration_days,
  }));
}