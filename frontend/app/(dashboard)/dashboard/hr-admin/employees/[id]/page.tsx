import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { EmployeeForm } from "@/components/hr/employee-form";
import { getCurrentUser } from "@/lib/auth";
import { getEmployee } from "@/lib/employees";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";
import { listTeams } from "@/lib/teams";
import type { TeamOption } from "@/lib/employees";

const TEAMS_ERROR =
  "Teams could not be loaded, so this employee's team cannot be changed. Reload the page to try again.";

export default async function EmployeeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let employee;
  try {
    employee = await getEmployee(id);
  } catch {
    notFound();
  }

  let gradeOptions: string[] = [];
  try {
    const entitlements = await listEntitlements();
    gradeOptions = gradeOptionsFromEntitlements(entitlements.results);
  } catch {
    // Manual grade entry remains available if entitlements cannot be loaded.
  }

  let teams: TeamOption[] = [];
  let teamsError = "";
  try {
    teams = await listTeams();
  } catch {
    teamsError = TEAMS_ERROR;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/employees"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to employees
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h2 className="text-2xl font-bold text-text-primary">
            {employee.full_name || employee.email}
          </h2>
          <span
            className={
              employee.is_active
                ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
            }
          >
            {employee.is_active ? "Active" : "Inactive"}
          </span>
        </div>
        <p className="text-text-secondary">{employee.email}</p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Profile details
        </h3>
        <EmployeeForm
          employee={employee}
          endpoint={`/api/hr/employees/${employee.id}`}
          method="PATCH"
          gradeOptions={gradeOptions}
          teams={teams}
          teamsError={teamsError}
        />
      </div>
    </div>
  );
}