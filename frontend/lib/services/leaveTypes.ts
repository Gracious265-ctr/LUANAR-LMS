export interface LeaveType {
  id: number;
  code: string;
  name: string;
  requiresDocuments: boolean;
  maxDurationDays: number | null;
  entitlementDays?: number | null;
}

interface LeaveTypeOptionsResponse {
  id: number;
  name: string;
  code: string;
  max_duration_days: number | null;
  requires_supporting_document: boolean;
  entitlement_days?: number | null;
}

<<<<<<< HEAD
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
=======
export async function getLeaveTypes(): Promise<LeaveType[]> {
  const res = await fetch("/api/leave/leave-types/");
  if (!res.ok) {
    throw new Error("Failed to load leave types");
  }

  const data = (await res.json()) as LeaveTypeOptionsResponse[];

  if (!Array.isArray(data)) {
    throw new Error("Failed to load leave types");
  }

  return data.map((t) => ({
    id: t.id,
    name: t.name,
    requiresDocuments: t.requires_supporting_document,
    maxDurationDays: t.max_duration_days,
    entitlementDays: t.entitlement_days ?? null,
>>>>>>> feature/plans-teams
  }));
}