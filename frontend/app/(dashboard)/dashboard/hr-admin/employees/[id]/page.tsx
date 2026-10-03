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
import { listDepartments, type Department } from "@/lib/departments";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const DEPARTMENTS_ERROR =
  "Departments could not be loaded, so this employee's department cannot be changed. Reload the page to try again.";

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

  let departments: Department[] = [];
  let departmentsError = "";
  try {
    departments = await listDepartments();
  } catch {
    departmentsError = DEPARTMENTS_ERROR;
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
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            {employee.full_name || employee.email}
          </h2>
          <Badge
            tone={employee.is_active ? "info" : "muted"}
          size="sm"
          className="font-medium"
        >
          {employee.is_active ? "Active" : "Inactive"}
        </Badge>
        </div>
        <p className="text-text-secondary">{employee.email}</p>
      </div>

      <Card>
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Profile details
        </h3>
        <EmployeeForm
          employee={employee}
          endpoint={`/api/hr/employees/${employee.id}`}
          method="PATCH"
          gradeOptions={gradeOptions}
          departments={departments}
          departmentsError={departmentsError}
        />
      </Card>
    </div>
  );
}