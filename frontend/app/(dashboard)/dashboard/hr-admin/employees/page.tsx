import { redirect } from "next/navigation";
import { Search } from "lucide-react";

import { EmployeesSection } from "@/components/hr/EmployeesSection";
import { getCurrentUser } from "@/lib/auth";
import type { EmployeeListResponse, TeamOption } from "@/lib/employees";
import { listEmployees } from "@/lib/employees";
import type { Team } from "@/lib/teams";
import { listTeams } from "@/lib/teams";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const TEAMS_ERROR = "Unable to load teams. Please try again.";

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

  // The create overlay needs its option set on the page. Retired teams are
  // included so the picker can say why a team would not route, and the grade
  // list comes from the entitlements rather than being typed, because a grade
  // that no entitlement uses is silently ignored downstream.
  const [teamsResult, gradeOptions] = await Promise.all([
    listTeams({ includeInactive: true }).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Team[], error: TEAMS_ERROR })
    ),
    listEntitlements()
      .then((entitlements) => gradeOptionsFromEntitlements(entitlements.results))
      .catch(() => [] as string[]),
  ]);

  return (
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
          teams={teamsResult.value as TeamOption[]}
          teamsError={teamsResult.error}
          search={query}
          error={error}
          filter={
            <form method="get" className="mb-4 flex max-w-md items-center gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                <Input
                  name="search"
                  defaultValue={query}
                  placeholder="Search name, email, department..."
                  className="pl-9 pr-3"
                />
              </div>
              <Button type="submit" variant="secondary">
                Search
              </Button>
            </form>
          }
        />
      </Card>
    </div>
  );
}