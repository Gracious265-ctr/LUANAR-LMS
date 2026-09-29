import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { EditActionLink } from "./edit-action-link";
import { EmptyState } from "@/components/ui/states";

export function LeaveTypeTable({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  if (leaveTypes.length === 0) {
    return (
      <EmptyState
        title="No leave types found"
        description="Add a leave type (such as annual, maternity, or paternity) to get started."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Name</th>
            <th className="py-3 pr-4">Code</th>
            <th className="py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {leaveTypes.map((leaveType) => (
            <tr
              key={leaveType.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/leave-types/${leaveType.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {leaveType.name}
                </Link>
              </td>
              <td className="py-3 pr-4 text-text-secondary">{leaveType.code}</td>
              <td className="py-3 text-right">
                <EditActionLink
                  href={`/dashboard/hr-admin/leave-types/${leaveType.id}/edit`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}