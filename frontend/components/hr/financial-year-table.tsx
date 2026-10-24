import Link from "next/link";

import type { FinancialYear } from "@/lib/financial-years";
import { deleteFinancialYear } from "@/lib/financial-years-client";
import { DeleteRowButton } from "./delete-row-button";
import { EmptyState } from "@/components/ui/states";
import { currentDateIso } from "@/lib/utils";
import { EditActionLink, EditIconButton } from "./edit-action-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function FinancialYearTable({
  years,
  onEdit,
  today = currentDateIso(),
}: {
  years: FinancialYear[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
  today?: string;
}) {
  if (years.length === 0) {
    return (
      <EmptyState
        title="No financial years configured"
        description="Add a financial year so leave applications can be validated against it."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Start</TableHead>
          <TableHead>End</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {years.map((year) => {
          const status =
            year.is_active
              ? "active"
              : year.start_date > today
                ? "upcoming"
                : "past";
          return (
            <TableRow
              key={year.id}
            >
              <TableCell>
                <Link
                  href={`/dashboard/hr-admin/calendar/financial-years/${year.id}/edit`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {year.start_date}
                </Link>
              </TableCell>
              <TableCell className="text-text-secondary">
                {year.end_date}
              </TableCell>
              <TableCell>
                <Badge
                  size="sm"
                  tone={
                    status === "active"
                      ? "info"
                      : status === "upcoming"
                        ? "brand"
                        : "muted"
                  }
                  className="font-medium"
                >
                  {status === "active"
                    ? "Active"
                    : status === "upcoming"
                      ? "Upcoming"
                      : "Past"}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="flex items-center justify-end gap-2">
                  {onEdit ? (
                    <EditIconButton
                      onClick={() => onEdit(year.id)}
                      label={`Edit ${year.start_date} financial year`}
                    />
                  ) : (
                    <EditActionLink
                      href={`/dashboard/hr-admin/calendar/financial-years/${year.id}/edit`}
                    />
                  )}
                  <DeleteRowButton
                    label={`Delete ${year.start_date} financial year`}
                    prompt={`Delete the ${year.start_date} – ${year.end_date} financial year?`}
                    onDelete={() => deleteFinancialYear(year.id)}
                  />
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}