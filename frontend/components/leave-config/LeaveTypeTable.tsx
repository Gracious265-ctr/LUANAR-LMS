import Link from "next/link";
import { FileText } from "lucide-react";

import {
  branchScopeLabel,
  colorHex,
  dayCountLabel,
  type LeaveType,
} from "@/lib/leave-config";
import { formatDisplayDate } from "@/lib/date";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * The registry as one table (spec 3.2) — the module's landing surface.
 *
 * Retired types stay in the list rather than moving to a page of their own:
 * they are greyed in place, so an HR of seven can see that a type was retired
 * instead of having to guess it never existed. The row's name is the link into
 * the edit view, which is what makes "row → Deactivate → Confirm" exactly the
 * three clicks the spec budgets.
 */
export function LeaveTypeTable({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  if (leaveTypes.length === 0) {
    return (
      <EmptyState
        title="No leave types configured yet"
        description="Leave, Plans and Approvals all read from this registry."
        action={
          <Link
            href="/leave-config/new"
            className="inline-flex h-control-height-md items-center gap-control-gap rounded-control border border-transparent bg-button-primary px-control-x-md text-sm font-medium text-button-primary-foreground transition-colors hover:bg-button-primary-hover focus-ring"
          >
            Create Leave Type
          </Link>
        }
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Branch scope</TableHead>
          <TableHead>Max duration</TableHead>
          <TableHead>Notice period</TableHead>
          <TableHead>Document</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last updated</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {leaveTypes.map((leaveType) => (
          <TableRow
            key={leaveType.id}
            data-inactive={!leaveType.is_active}
            className={cn(!leaveType.is_active && "opacity-60")}
          >
            <TableCell>
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block size-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: colorHex(leaveType.color) }}
                />
                <Link
                  href={`/leave-config/${leaveType.id}`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {leaveType.name}
                </Link>
              </span>
            </TableCell>
            <TableCell>{branchScopeLabel(leaveType.branch_scope)}</TableCell>
            <TableCell>
              {dayCountLabel(leaveType.max_duration_days, "No maximum")}
            </TableCell>
            <TableCell>
              {dayCountLabel(leaveType.notice_days, "No minimum")}
            </TableCell>
            <TableCell>
              {leaveType.requires_supporting_document ? (
                <>
                  <FileText className="h-4 w-4 text-text-secondary" aria-hidden="true" />
                  <span className="sr-only">Supporting document required</span>
                </>
              ) : (
                <>
                  <span aria-hidden="true" className="text-text-muted">
                    —
                  </span>
                  <span className="sr-only">No supporting document required</span>
                </>
              )}
            </TableCell>
            <TableCell>
              <Badge
                size="sm"
                tone={leaveType.is_active ? "info" : "muted"}
                className="font-medium"
              >
                {leaveType.is_active ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell className="whitespace-nowrap text-text-muted">
              {formatDisplayDate(leaveType.updated_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
