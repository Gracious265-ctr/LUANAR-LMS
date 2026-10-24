import Link from "next/link";

import type { FinancialYear, Holiday } from "@/lib/financial-years";
import { deleteHoliday } from "@/lib/financial-years-client";
import { DeleteRowButton } from "./delete-row-button";
import { EditActionLink, EditIconButton } from "./edit-action-link";
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

export function HolidayTable({
  holidays,
  financialYears = [],
  onEdit,
}: {
  holidays: Holiday[];
  /** Resolves a holiday's `financial_year` id to a readable label. */
  financialYears?: FinancialYear[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (holidays.length === 0) {
    return (
      <EmptyState
        title="No holidays"
        description="Add the dates that should not count as working leave days."
      />
    );
  }

  const yearLabel = (id: number | null) => {
    if (id === null) return "Institution-wide";
    const year = financialYears.find((row) => row.id === id);
    return year ? `${year.start_date} – ${year.end_date}` : `Year ${id}`;
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Date</TableHead>
          <TableHead>Recurring</TableHead>
          <TableHead>Scope</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {holidays.map((holiday) => (
          <TableRow key={holiday.id}>
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/calendar/holidays/${holiday.id}/edit`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {holiday.name}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">{holiday.date}</TableCell>
            <TableCell>
              <Badge size="sm" tone={holiday.is_recurring ? "brand" : "muted"}>
                {holiday.is_recurring ? "Yearly" : "One-off"}
              </Badge>
            </TableCell>
            <TableCell className="text-text-secondary">
              {yearLabel(holiday.financial_year)}
            </TableCell>
            <TableCell>
              <div className="flex items-center justify-end gap-2">
                {onEdit ? (
                  <EditIconButton
                    onClick={() => onEdit(holiday.id)}
                    label={`Edit ${holiday.name}`}
                  />
                ) : (
                  <EditActionLink
                    href={`/dashboard/hr-admin/calendar/holidays/${holiday.id}/edit`}
                  />
                )}
                <DeleteRowButton
                  label={`Delete ${holiday.name}`}
                  prompt={`Delete ${holiday.name}?`}
                  onDelete={() => deleteHoliday(holiday.id)}
                />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
