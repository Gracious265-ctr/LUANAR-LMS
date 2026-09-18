import Link from "next/link";

import type { FinancialYear } from "@/lib/financial-years";
import { currentDateIso } from "@/lib/utils";

export function FinancialYearTable({
  years,
  today = currentDateIso(),
}: {
  years: FinancialYear[];
  today?: string;
}) {
  if (years.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No financial years configured
        </p>
        <p className="mt-1 text-sm">
          Add a financial year so leave applications can be validated against
          it.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Start</th>
            <th className="py-3 pr-4">End</th>
            <th className="py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year) => {
            const status =
              year.is_active
                ? "active"
                : year.start_date > today
                  ? "upcoming"
                  : "past";
            return (
              <tr
                key={year.id}
                className="border-b border-border-default transition-colors hover:bg-surface-hover"
              >
                <td className="py-3 pr-4">
                  <Link
                    href={`/dashboard/hr-admin/calendar/financial-years/${year.id}/edit`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {year.start_date}
                  </Link>
                </td>
                <td className="py-3 pr-4 text-text-secondary">
                  {year.end_date}
                </td>
                <td className="py-3">
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
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}