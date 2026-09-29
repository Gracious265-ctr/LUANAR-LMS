import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { EmployeeForm } from "@/components/hr/employee-form";
import { getCurrentUser } from "@/lib/auth";
import { listEmployees } from "@/lib/employees";
import {
  gradeOptionsFromEntitlements,
  listEntitlements,
} from "@/lib/entitlements";

const SUPERVISOR_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];

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

  let supervisorOptions: { id: number; full_name: string }[] = [];
  try {
    const employees = await listEmployees();
    supervisorOptions = employees.results
      .filter((employee) => SUPERVISOR_ROLES.includes(employee.role))
      .map((employee) => ({
        id: employee.user_id,
        full_name: employee.full_name,
      }));
  } catch {
    // The supervisor field remains optional if the option list cannot load.
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
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">New employee</h2>
        <p className="text-text-secondary">
          Create an employee record. A login account is created automatically.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <EmployeeForm
          endpoint="/api/hr/employees"
          method="POST"
          gradeOptions={gradeOptions}
          supervisorOptions={supervisorOptions}
        />
      </div>
    </div>
  );
}