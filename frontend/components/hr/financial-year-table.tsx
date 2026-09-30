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
import { Badge } from "@/components/ui/badge";

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