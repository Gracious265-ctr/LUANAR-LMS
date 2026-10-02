import Link from "next/link";
import { redirect } from "next/navigation";

import { FinancialYearsSection } from "@/components/hr/FinancialYearsSection";
import { HolidaysSection } from "@/components/hr/HolidaysSection";
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
import { Card } from "@/components/ui/card";

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

      <Card>
        {yearsError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {yearsError}
          </div>
        ) : financialYears ? (
          <FinancialYearsSection years={financialYears.results} />
        ) : null}
      </Card>

      <Card>
        {holidaysError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {holidaysError}
          </div>
        ) : holidays ? (
          <HolidaysSection
            holidays={holidays.results}
            yearFilter={yearFilter}
            filter={
              /*
                A plain GET form, so submitting it navigates to the `year`
                parameter alone and drops any open overlay key. That is harmless
                today because the filter sits behind the modal and cannot be
                reached while it is open; it would need to carry the overlay key
                forward if the two ever became usable together.
              */
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
            }
          />
        ) : null}
      </Card>
    </div>
  );
}
