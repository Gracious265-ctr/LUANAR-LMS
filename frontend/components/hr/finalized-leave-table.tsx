import Link from "next/link";

import type { FinalizedApplication } from "@/lib/audit";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Reference</TableHead>
          <TableHead>Employee</TableHead>
          <TableHead>Leave type</TableHead>
          <TableHead>Dates</TableHead>
          <TableHead>Current approver</TableHead>
          <TableHead>Submitted</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {applications.map((app) => (
          <TableRow
            key={app.id}
          >
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/audit/applications/${app.id}`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {app.reference_number || "\u2014"}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">
              {app.employee_name}
            </TableCell>
            <TableCell className="text-text-secondary">
              {app.leave_type_name || "\u2014"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {app.start_date && app.end_date
                ? `${app.start_date} \u2192 ${app.end_date}`
                : app.start_date ?? "\u2014"}
              {app.calculated_days != null && (
                <span className="ml-1 text-xs text-text-muted">
                  ({app.calculated_days}d)
                </span>
              )}
            </TableCell>
            <TableCell>
              {app.current_approver ? (
                <span className="inline-block rounded-full bg-brand-primary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-primary">
                  {app.current_approver_name}
                </span>
              ) : (
                <span className="inline-block rounded-full bg-status-pending-subtle px-2.5 py-0.5 text-xs font-medium text-status-pending">
                  Unassigned
                </span>
              )}
            </TableCell>
            <TableCell className="text-text-secondary">
              {app.submitted_at
                ? new Date(app.submitted_at).toLocaleDateString()
                : "\u2014"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}