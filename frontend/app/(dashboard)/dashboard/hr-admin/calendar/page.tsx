import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { FinancialYearTable } from "@/components/hr/financial-year-table";
import { PublicHolidayTable } from "@/components/hr/public-holiday-table";
import { getCurrentUser } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  listFinancialYears,
  listPublicHolidays,
} from "@/lib/financial-years";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default async function CalendarPage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const params = await searchParams;
  const yearFilter =
    typeof params.year === "string" && params.year ? params.year : "";

  let financialYears;
  let yearsError = "";
  try {
    financialYears = await listFinancialYears();
  } catch {
    yearsError = "Unable to load financial years. Please try again.";
  }

  let holidays;
  let holidaysError = "";
  try {
    holidays = await listPublicHolidays(yearFilter || undefined);
  } catch {
    holidaysError = "Unable to load public holidays. Please try again.";
  }

  const availableYears = Array.from(
    new Set((financialYears?.results ?? []).map((year) => year.start_date.slice(0, 4)))
  ).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">Leave calendar</h2>
        <p className="text-text-secondary">
          Configure the university&apos;s financial years and public holidays.
          The system uses the active financial year when validating leave
          applications, and public holidays do not count as working leave days.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              Financial years
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Exactly one period is active at a time; future periods are
              scheduled by activating them.
            </p>
          </div>
          <Link
            href="/dashboard/hr-admin/calendar/financial-years/new"
            className="inline-flex shrink-0 items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            <Plus className="h-4 w-4" />
            New financial year
          </Link>
        </div>

        {yearsError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {yearsError}
          </div>
        ) : financialYears ? (
          <FinancialYearTable years={financialYears.results} />
        ) : null}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              Public holidays
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Dates that should not count as working leave days.
            </p>
          </div>
          <Link
            href="/dashboard/hr-admin/calendar/holidays/new"
            className="inline-flex shrink-0 items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            <Plus className="h-4 w-4" />
            New holiday
          </Link>
        </div>

        <form method="get" className="mb-4 flex items-center gap-2">
          <Select name="year" defaultValue={yearFilter}>
            <SelectTrigger size="sm" aria-label="Year" className="w-auto py-1.5">
              <SelectValue placeholder="All years" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All years</SelectItem>
              {availableYears.map((year) => (
                <SelectItem key={year} value={year}>
                  {year}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="submit" variant="secondary" size="sm">
            Filter
          </Button>
          {yearFilter && (
            <Link
              href="/dashboard/hr-admin/calendar"
              className="rounded-md px-2 py-1.5 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
            >
              Clear
            </Link>
          )}
        </form>

        {holidaysError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {holidaysError}
          </div>
        ) : holidays ? (
          <PublicHolidayTable holidays={holidays.results} />
        ) : null}
      </div>
    </div>
  );
}