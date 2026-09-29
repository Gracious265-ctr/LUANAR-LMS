import Link from "next/link";

import type { FinalizedApplication } from "@/lib/audit";
import { EmptyState } from "@/components/ui/states";

export function FinalizedLeaveTable({
  applications,
}: {
  applications: FinalizedApplication[];
}) {
  if (applications.length === 0) {
    return (
      <EmptyState
        title="No finalized applications"
        description="Submitted leave applications organization-wide appear here once employees submit them."
      />
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
            <th className="py-3">Submitted</th>
          </tr>
        </thead>
        <tbody>
          {applications.map((app) => (
            <tr
              key={app.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/audit/applications/${app.id}`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {app.reference_number || "\u2014"}
                </Link>
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
              <td className="py-3 text-text-secondary">
                {app.submitted_at
                  ? new Date(app.submitted_at).toLocaleDateString()
                  : "\u2014"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}