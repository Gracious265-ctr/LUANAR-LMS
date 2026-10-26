import type { Reassignment } from "@/lib/reassignments";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function ReassignmentTable({
  reassignments,
}: {
  reassignments: Reassignment[];
}) {
  if (reassignments.length === 0) {
    return (
      <EmptyState
        title="No reassignments yet"
        description="Reassign a pending application to record the first reassignment."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Application</TableHead>
          <TableHead>Employee</TableHead>
          <TableHead>From → To</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead>Decided</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {reassignments.map((reassignment) => (
          <TableRow
            key={reassignment.id}
          >
            <TableCell className="font-medium text-text-primary">
              {reassignment.reference_number || "\u2014"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {reassignment.employee_name}
            </TableCell>
            <TableCell className="text-text-secondary">
              <span className="text-text-muted">
                {reassignment.from_approver_name || "Unassigned"}
              </span>
              <span className="mx-1 text-text-muted">→</span>
              <span className="font-medium text-text-primary">
                {reassignment.to_approver_name}
              </span>
            </TableCell>
            <TableCell className="text-text-secondary">
              {reassignment.reason}
            </TableCell>
            <TableCell className="text-text-secondary">
              <div>{reassignment.decided_by_name}</div>
              <div className="text-xs text-text-muted">
                {new Date(reassignment.created_at).toLocaleString()}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}