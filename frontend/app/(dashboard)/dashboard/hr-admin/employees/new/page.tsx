import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { EmployeeForm } from "@/components/hr/employee-form";
import { getCurrentUser } from "@/lib/auth";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";
import { listTeams } from "@/lib/teams";
import type { TeamOption } from "@/lib/employees";

const TEAMS_ERROR =
  "Teams could not be loaded, so this employee cannot be placed in a team. Reload the page, or create a team first.";

export default async function NewEmployeePage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
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
        <h2 className="mt-2 text-2xl font-bold text-text-primary">New employee</h2>
        <p className="text-text-secondary">
          Create an employee record. A login account is created automatically.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <EmployeeForm
          endpoint="/api/hr/employees"
          method="POST"
          gradeOptions={gradeOptions}
          teams={teams}
          teamsError={teamsError}
        />
      </div>
    </div>
  );
}