import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ApproverRoleForm } from "@/components/hr/approver-role-form";
import { getApproverRole } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";

export default async function EditRolePage({
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

  let role;
  try {
    role = await getApproverRole(id);
  } catch {
    notFound();
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
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          Edit {role.label}
        </h2>
        <p className="text-text-secondary">
          Rename the role or change how much leave history it sees. Whether the
          role is institution-wide is decided on the Approvers page, where its
          holder is assigned — not here. Retiring is a separate action from the
          roles list, and only allowed once nothing uses the role.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <ApproverRoleForm role={role} />
      </div>
    </div>
  );
}
