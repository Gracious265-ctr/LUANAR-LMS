import Link from "next/link";

import { CalendarTabs, type CalendarTab } from "@/components/hr/CalendarTabs";
import { CalendarMonthGrid } from "@/components/hr/CalendarMonthGrid";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";
import {
  listCalendarEvents,
  listFinancialYears,
  listHolidays,
  listResolvedHolidays,
  getWorkingDayPattern,
  requireCalendarAccess,
  type ResolvedHoliday,
} from "@/lib/financial-years";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function parseMonth(value: string | undefined): { year: number; month: number } {
  if (value && /^\d{4}-\d{2}$/.test(value)) {
    const [year, month] = value.split("-").map(Number);
    if (month >= 1 && month <= 12) {
      return { year, month };
    }
  }
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function shiftMonth(
  { year, month }: { year: number; month: number },
  delta: number
): string {
  const date = new Date(Date.UTC(year, month - 1 + delta, 1));
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}`;
}

export default async function CalendarPage({
  searchParams,
}: {
  searchParams: Promise<{
    year?: string | string[];
    tab?: string | string[];
    month?: string | string[];
    holiday?: string | string[];
    event?: string | string[];
    financialYear?: string | string[];
    workingDays?: string | string[];
  }>;
}) {
  await requireCalendarAccess();

  const params = await searchParams;
  const first = (value: string | string[] | undefined) =>
    typeof value === "string" && value ? value : "";

  const yearFilter = first(params.year);
  const grid = parseMonth(first(params.month) || undefined);

  // A deep link to an overlay should land on the tab that hosts it, so the
  // dialog and the table it belongs to are visible together.
  const requestedTab = first(params.tab);
  const overlayTab: CalendarTab | "" =
    first(params.financialYear)
      ? "financial-years"
      : first(params.holiday) || first(params.event)
        ? "holidays"
        : first(params.workingDays)
          ? "working-days"
          : "";
  const initialTab: CalendarTab =
    requestedTab === "holidays" ||
    requestedTab === "working-days" ||
    requestedTab === "financial-years"
      ? requestedTab
      : overlayTab || "financial-years";

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
    holidays = await listHolidays(yearFilter || undefined);
  } catch {
    holidaysError = "Unable to load holidays. Please try again.";
  }

  let events;
  try {
    events = await listCalendarEvents();
  } catch {
    events = { count: 0, next: null, previous: null, results: [] };
  }

  let workingDays;
  try {
    workingDays = await getWorkingDayPattern();
  } catch {
    workingDays = {
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: false,
      sunday: false,
    };
  }

  const daysInMonth = new Date(Date.UTC(grid.year, grid.month, 0)).getUTCDate();
  let resolvedHolidays: ResolvedHoliday[] = [];
  try {
    resolvedHolidays = await listResolvedHolidays(
      `${grid.year}-${pad(grid.month)}-01`,
      `${grid.year}-${pad(grid.month)}-${pad(daysInMonth)}`
    );
  } catch {
    resolvedHolidays = [];
  }

  const availableYears = Array.from(
    new Set((financialYears?.results ?? []).map((year) => year.start_date.slice(0, 4)))
  ).sort((a, b) => b.localeCompare(a));

  const gridNav = (delta: number, label: string) => (
    <Link
      href={`/dashboard/hr-admin/calendar?tab=holidays&month=${shiftMonth(grid, delta)}`}
      className="rounded-md border border-border-default px-2 py-1 text-xs font-medium text-text-secondary hover:text-text-primary"
    >
      {label}
    </Link>
  );

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Calendar
          </h2>
          <p className="text-text-secondary">Configure financial years, holidays, events, and working days.</p>
        </div>

        {yearsError ? (
          <Card>
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {yearsError}
            </div>
          </Card>
        ) : (
          <CalendarTabs
            initialTab={initialTab}
            financialYears={financialYears?.results ?? []}
            holidays={holidays?.results ?? []}
            holidayYearFilter={yearFilter}
            events={events.results}
            workingDays={workingDays}
            grid={
              <div className="space-y-2">
                <div className="flex items-center justify-end gap-2">
                  {gridNav(-1, "Previous month")}
                  {gridNav(1, "Next month")}
                </div>
                <CalendarMonthGrid
                  year={grid.year}
                  month={grid.month}
                  holidays={resolvedHolidays}
                  events={events.results}
                  workingDays={workingDays}
                />
              </div>
            }
            holidayFilter={
              <form method="get" className="mb-4 flex items-center gap-2">
                <input type="hidden" name="tab" value="holidays" />
                <input
                  type="hidden"
                  name="month"
                  value={`${grid.year}-${pad(grid.month)}`}
                />
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
                    href="/dashboard/hr-admin/calendar?tab=holidays"
                    className="rounded-md px-2 py-1.5 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Clear
                  </Link>
                )}
              </form>
            }
          />
        )}

        {holidaysError && (
          <p className="text-sm text-status-rejected">{holidaysError}</p>
        )}
      </div>
    </FadeIn>
  );
}
