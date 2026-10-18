import { redirect } from "next/navigation";

import { EmployeesSection } from "@/components/hr/EmployeesSection";
import { getCurrentUser } from "@/lib/auth";
import type { EmployeeListResponse } from "@/lib/employees";
import { listEmployees } from "@/lib/employees";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";
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
    redirect("/");
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
          />
        </Card>
      </div>
    </FadeIn>
  );
}