import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { LeaveTypeForm } from "@/components/hr/leave-type-form";
import { getCurrentUser } from "@/lib/auth";

export default async function NewLeaveTypePage() {
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
          href="/dashboard/hr-admin/leave-types"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to leave types
        </Link>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
          New leave type
        </h2>
        <p className="text-text-secondary">
          Add a leave type such as annual, maternity, or a university-specific
          type. The code is optional and derived from the name when left blank.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <LeaveTypeForm />
      </div>
    </div>
  );
}