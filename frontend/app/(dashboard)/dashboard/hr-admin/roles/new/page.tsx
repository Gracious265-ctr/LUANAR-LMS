import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ApproverRoleForm } from "@/components/hr/approver-role-form";
import { getCurrentUser } from "@/lib/auth";

export default async function NewRolePage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/roles"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to roles
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">New role</h2>
        <p className="text-text-secondary">
          Define an approver position. Once it exists you can name it in a
          workflow stage, staff it on a team, or give one person it
          institution-wide.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <ApproverRoleForm />
      </div>
    </div>
  );
}
