import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { DepartmentTable } from "@/components/hr/department-table";
import { getCurrentUser } from "@/lib/auth";
import { listDepartments } from "@/lib/departments";

export default async function DepartmentsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "hr") redirect("/dashboard");

  const departments = await listDepartments(true);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">
            Departments
          </h2>
          <p className="text-text-secondary">
            The units your teams and employees belong to.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/departments/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New department
        </Link>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <DepartmentTable departments={departments} />
      </div>
    </div>
  );
}
