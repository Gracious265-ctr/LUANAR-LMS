import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { isAnnualLeaveType } from "@/lib/leave-rules-pure";
import { EditActionLink, EditIconButton } from "./edit-action-link";
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

export function LeaveTypeTable({
  leaveTypes,
  onEdit,
}: {
  leaveTypes: LeaveType[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (leaveTypes.length === 0) {
    return (
      <EmptyState
        title="No leave types found"
        description="Add a leave type (such as maternity, paternity, or compassionate) to get started. Annual leave is created for you when you add an entitlement."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {leaveTypes.map((leaveType) => {
          const annual = isAnnualLeaveType(leaveType);
          const editHref = `/hr-admin/leave-types/${leaveType.id}/edit`;

          return (
            <TableRow key={leaveType.id}>
              <TableCell>
                {annual ? (
                  <span className="font-medium text-text-primary">
                    {leaveType.name}
                  </span>
                ) : (
                  <Link
                    href={editHref}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {leaveType.name}
                  </Link>
                )}
              </TableCell>
              <TableCell className="text-text-secondary">{leaveType.code}</TableCell>
              <TableCell>
                {annual ? (
                  <Badge size="sm" tone="muted" className="font-medium">
                    Managed in Entitlements
                  </Badge>
                ) : (
                  <Badge
                    size="sm"
                    tone={leaveType.is_active !== false ? "info" : "muted"}
                    className="font-medium"
                  >
                    {leaveType.is_active !== false ? "Active" : "Inactive"}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                {annual ? (
                  <Link
                    href="/hr-admin/entitlements"
                    className="text-xs text-text-muted underline underline-offset-2 hover:text-text-primary"
                  >
                    Edit days
                  </Link>
                ) : onEdit ? (
                  <EditIconButton
                    onClick={() => onEdit(leaveType.id)}
                    label={`Edit ${leaveType.name}`}
                  />
                ) : (
                  <EditActionLink href={editHref} />
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}