import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";

import type { PendingApplication } from "@/lib/reassignments";

export function PendingApplicationsTable({
  applications,
}: {
  applications: PendingApplication[];
}) {
  if (applications.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No pending applications
        </p>
        <p className="mt-1 text-sm">
          All submitted applications are either assigned or no leave applications
          have been submitted yet.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Reference</th>
            <th className="py-3 pr-4">Employee</th>
            <th className="py-3 pr-4">Leave type</th>
            <th className="py-3 pr-4">Dates</th>
            <th className="py-3 pr-4">Current approver</th>
            <th className="py-3" />
          </tr>
        </thead>
        <tbody>
          {applications.map((app) => (
            <tr
              key={app.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4 font-medium text-text-primary">
                {app.reference_number || "\u2014"}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {app.employee_name}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {app.leave_type_name || "\u2014"}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {app.start_date && app.end_date
                  ? `${app.start_date} \u2192 ${app.end_date}`
                  : app.start_date ?? "\u2014"}
                {app.calculated_days != null && (
                  <span className="ml-1 text-xs text-text-muted">
                    ({app.calculated_days}d)
                  </span>
                )}
              </td>
              <td className="py-3 pr-4">
                {app.current_approver ? (
                  <span className="inline-block rounded-full bg-brand-primary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-primary">
                    {app.current_approver_name}
                  </span>
                ) : (
                  <span className="inline-block rounded-full bg-status-pending-subtle px-2.5 py-0.5 text-xs font-medium text-status-pending">
                    Unassigned
                  </span>
                )}
              </td>
              <td className="py-3 text-right">
                <Link
                  href={`/dashboard/hr-admin/reassignments/new?application=${app.id}`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" />
                  Reassign
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}