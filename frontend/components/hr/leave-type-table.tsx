import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { EditActionLink } from "./edit-action-link";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Code</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {leaveTypes.map((leaveType) => (
          <TableRow
            key={leaveType.id}
          >
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/leave-types/${leaveType.id}/edit`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {leaveType.name}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">{leaveType.code}</TableCell>
            <TableCell className="text-right">
              <EditActionLink
                href={`/dashboard/hr-admin/leave-types/${leaveType.id}/edit`}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}