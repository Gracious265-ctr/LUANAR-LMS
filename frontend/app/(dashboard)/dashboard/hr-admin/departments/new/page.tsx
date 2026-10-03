import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { DepartmentForm } from "@/components/hr/department-form";
import { getCurrentUser } from "@/lib/auth";

export default async function NewDepartmentPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "hr") redirect("/dashboard");

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
          New department
        </h2>
        <p className="text-text-secondary">
          A department is what scopes a team&apos;s approvers: only its own
          employees may hold a stage on one of its teams.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <DepartmentForm />
      </div>
    </div>
  );
}
