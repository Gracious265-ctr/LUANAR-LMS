import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { LeaveTypeForm } from "@/components/hr/leave-type-form";
import { getCurrentUser } from "@/lib/auth";
import { getLeaveType } from "@/lib/leave-rules";

export default async function EditLeaveTypePage({
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

  let leaveType;
  try {
    leaveType = await getLeaveType(id);
  } catch {
    notFound();
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
          Edit leave type
        </h2>
        <p className="text-text-secondary">
          Update the name or code for {leaveType.name}.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <LeaveTypeForm leaveType={leaveType} />
      </div>
    </div>
  );
}