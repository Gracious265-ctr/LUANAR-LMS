import Link from "next/link";

import type { FinancialYear } from "@/lib/financial-years";
import { EmptyState } from "@/components/ui/states";
import { currentDateIso } from "@/lib/utils";
import { EditActionLink } from "./edit-action-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function FinancialYearTable({
  years,
  today = currentDateIso(),
}: {
  years: FinancialYear[];
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
                <span
                  className={
                    status === "active"
                      ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                      : status === "upcoming"
                        ? "inline-block rounded-full bg-brand-primary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-primary"
                        : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                  }
                >
                  {status === "active"
                    ? "Active"
                    : status === "upcoming"
                      ? "Upcoming"
                      : "Past"}
                </span>
              </TableCell>
              <TableCell className="text-right">
                <EditActionLink
                  href={`/dashboard/hr-admin/calendar/financial-years/${year.id}/edit`}
                />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}