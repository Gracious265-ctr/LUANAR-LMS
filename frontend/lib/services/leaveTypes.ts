export interface LeaveType {
  id: number;
  name: string;
  requiresDocuments: boolean;
  maxDurationDays: number | null;
}

export async function getLeaveTypes(): Promise<LeaveType[]> {
  // TODO(unit-4): replace with fetch('/api/leave-types/')
  return [
    { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: null },
    { id: 2, name: "Maternity Leave", requiresDocuments: true, maxDurationDays: 90 },
    { id: 3, name: "Paternity Leave", requiresDocuments: true, maxDurationDays: 14 },
    { id: 4, name: "Compassionate Leave", requiresDocuments: true, maxDurationDays: 7 },
  ];
}
