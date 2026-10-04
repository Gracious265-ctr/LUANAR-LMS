import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { EditActionLink } from "./edit-action-link";

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
            <th className="py-3 pr-4">Code</th>
            <th className="py-3 pr-4">Status</th>
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
              <td className="py-3 pr-4">
                <span
                  className={
                    leaveType.is_active !== false
                      ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                      : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                  }
                >
                  {leaveType.is_active !== false ? "Active" : "Inactive"}
                </span>
              </td>
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