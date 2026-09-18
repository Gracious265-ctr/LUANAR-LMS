import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";

export function LeaveTypeTable({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  if (leaveTypes.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No leave types found
        </p>
        <p className="mt-1 text-sm">
          Add a leave type (such as annual, maternity, or paternity) to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Name</th>
            <th className="py-3">Code</th>
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
              <td className="py-3 text-text-secondary">{leaveType.code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}