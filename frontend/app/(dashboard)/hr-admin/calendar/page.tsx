import { redirect } from "next/navigation";

import { FinancialYearsSection } from "@/components/hr/FinancialYearsSection";
import { HolidaysSection } from "@/components/hr/HolidaysSection";
import { getCurrentUser } from "@/lib/auth";
import {
  listFinancialYears,
  listPublicHolidays,
} from "@/lib/financial-years";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

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
    redirect("/");
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
    <FadeIn>
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
              availableYears={availableYears}
            />
          ) : null}
        </Card>
      </div>
    </FadeIn>
  );
}
