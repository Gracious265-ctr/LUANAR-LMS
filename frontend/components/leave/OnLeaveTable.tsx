import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateRange } from "@/lib/date";
import { ON_LEAVE_STATE, type OnLeaveRow } from "@/lib/on-leave";

/**
 * Approved leave, one row per application.
 *
 * Presentational on purpose: the page owns the fetch and the filters, this only
 * renders what the backend allowed the viewer to see. The employee column is
 * always shown — every rung but "self" reads other people, and "self" reads like
 * any other list.
 */
export function OnLeaveTable({ rows }: { rows: OnLeaveRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Employee</TableHead>
          <TableHead>Leave</TableHead>
          <TableHead>Dates</TableHead>
          <TableHead>Days</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const state = ON_LEAVE_STATE[row.state];
          const context = [row.employee.designation, row.employee.team, row.employee.campus]
            .filter(Boolean)
            .join(" · ");
          return (
            <TableRow key={row.id}>
              <TableCell>
                <p className="font-medium text-text-primary">
                  {row.employee.full_name}
                </p>
                {context && (
                  <p className="text-xs text-text-muted">{context}</p>
                )}
              </TableCell>
              <TableCell className="whitespace-nowrap text-text-primary">
                {row.leave_type.name || "—"}
              </TableCell>
              <TableCell className="whitespace-nowrap">
                {formatDateRange(row.start_date, row.end_date) || "—"}
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums text-text-secondary">
                {row.working_days === null
                  ? "—"
                  : `${row.working_days} ${row.working_days === 1 ? "day" : "days"}`}
              </TableCell>
              <TableCell>
                <Badge tone={state.tone} size="sm">
                  {state.label}
                </Badge>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
