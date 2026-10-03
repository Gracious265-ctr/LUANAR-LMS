import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { DepartmentForm } from "@/components/hr/department-form";
import { getCurrentUser } from "@/lib/auth";
import { getDepartment } from "@/lib/departments";

export default async function EditDepartmentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "hr") redirect("/dashboard");

  const { id } = await params;

  let department;
  try {
    department = await getDepartment(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/departments"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to departments
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          {department.name}
        </h2>
        <p className="text-text-secondary">
          Rename the department, or retire it once nothing uses it.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <DepartmentForm department={department} />
      </div>
    </div>
  );
}
