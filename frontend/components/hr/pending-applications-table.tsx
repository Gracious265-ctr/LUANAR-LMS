import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";

import type { PendingApplication } from "@/lib/reassignments";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { STATUS_STYLES } from "@/lib/status-styles";
import { cn } from "@/lib/utils";

/**
 * The queue of applications with no assigned approver.
 *
 * With `onReassign` the row's action opens the overlay instead of navigating,
 * and it names the application because one bare "Reassign" per row would be
 * indistinguishable to a screen reader. Without it the row keeps the plain
 * link to the standalone form.
 */
export function PendingApplicationsTable({
  applications,
  onReassign,
}: {
  applications: PendingApplication[];
  onReassign?: (application: PendingApplication) => void;
}) {
  if (applications.length === 0) {
    return (
      <EmptyState
        title="No pending applications"
        description="No submitted applications are awaiting a decision."
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
          <TableHead>Acting for them</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {applications.map((app) => (
          <TableRow
            key={app.id}
          >
            <TableCell className="font-medium text-text-primary">
              {app.reference_number || "\u2014"}
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
                <Badge
                  size="sm"
                  tone="brand"
                  className="font-medium"
                >
                  {app.current_approver_name}
                </Badge>
              ) : (
                <Badge
                  size="sm"
                  tone="pending"
                  className="font-medium"
                >
                  Unassigned
                </Badge>
              )}
            </TableCell>
            <TableCell>
              {app.is_delegated ? (
                /* Spelled out rather than a bare name: reassigning to someone
                   who is away does not move the work to them, and this is the
                   one place HR can see that before acting. */
                <span className="inline-flex flex-col gap-0.5">
                  <span
                    className={cn(
                      "inline-block w-fit rounded-sm px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES.pending
                    )}
                  >
                    {app.acting_approver_name}
                  </span>
                  <span className="text-xs text-text-muted">
                    cover for {app.current_approver_name}
                  </span>
                </span>
              ) : (
                <span className="text-xs text-text-muted">
                  {app.acting_approver ? "—" : ""}
                </span>
              )}
            </TableCell>
            <TableCell className="text-right">
              {onReassign ? (
                <button
                  type="button"
                  onClick={() => onReassign(app)}
                  aria-label={`Reassign ${app.reference_number || app.employee_name}`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden="true" />
                  Reassign
                </button>
              ) : (
                <Link
                  href={`/dashboard/hr-admin/reassignments/new?application=${app.id}`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" />
                  Reassign
                </Link>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}