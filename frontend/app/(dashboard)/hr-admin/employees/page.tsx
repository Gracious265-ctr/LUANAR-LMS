import { redirect } from "next/navigation";
import { Search } from "lucide-react";

import { EmployeesSection } from "@/components/hr/EmployeesSection";
import { getCurrentUser } from "@/lib/auth";
import type { EmployeeListResponse } from "@/lib/employees";
import { listEmployees } from "@/lib/employees";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { search } = await searchParams;
  const query = typeof search === "string" ? search : "";
  let error = "";
  let employees: EmployeeListResponse | undefined;

  try {
    employees = await listEmployees(query);
  } catch {
    error = "Unable to load employees. Please try again.";
  }

  // The create overlay needs its option set on the page. Teams are filled from
  // the team side, so the only option here is the grade list, which comes from
  // the entitlements rather than being typed, because a grade that no
  // entitlement uses is silently ignored downstream.
  const gradeOptions = await listEntitlements()
    .then((entitlements) => gradeOptionsFromEntitlements(entitlements.results))
    .catch(() => [] as string[]);

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Employees</h2>
          <p className="text-text-secondary">
            Search and manage employee records.
          </p>
        </div>

        <Card>
          <EmployeesSection
            employees={employees?.results ?? []}
            totalCount={employees?.count ?? 0}
            gradeOptions={gradeOptions}
            search={query}
            error={error}
            filter={
              // This JSX is authored in a server component and rendered inside the
              // client `EmployeesSection`, so it crosses the RSC boundary. The
              // boundary re-creates these elements without the dev runtime's
              // "written as static siblings" flag, which makes React treat them as
              // a list and demand keys. The keys below are what satisfies that;
              // without them React warns "Each child in a list should have a
              // unique key prop" and names this section.
              <form method="get" className="mb-4 flex max-w-md items-center gap-2">
                <div key="search-field" className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                  <Input
                    name="search"
                    defaultValue={query}
                    placeholder="Search name, email, team..."
                    className="pl-9 pr-3"
                  />
                </div>
                <Button key="search-submit" type="submit" variant="secondary">
                  Search
                </Button>
              </form>
            }
          />
        </Card>
      </div>
    </FadeIn>
  );
}