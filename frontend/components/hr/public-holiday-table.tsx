import Link from "next/link";

import type { PublicHoliday } from "@/lib/financial-years";
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

export function PublicHolidayTable({
  holidays,
  onEdit,
}: {
  holidays: PublicHoliday[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (holidays.length === 0) {
    return (
      <EmptyState
        title="No public holidays"
        description="Add the dates that should not count as working leave days."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {holidays.map((holiday) => (
          <TableRow
            key={holiday.id}
          >
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/calendar/holidays/${holiday.id}/edit`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {holiday.name}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">{holiday.date}</TableCell>
            <TableCell className="text-right">
              {onEdit ? (
                <EditIconButton
                  onClick={() => onEdit(holiday.id)}
                  label={`Edit ${holiday.name}`}
                />
              ) : (
                <EditActionLink href={`/dashboard/hr-admin/calendar/holidays/${holiday.id}/edit`} />
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}