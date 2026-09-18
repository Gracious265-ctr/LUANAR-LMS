import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { LeaveRuleForm } from "@/components/hr/leave-rule-form";
import { getCurrentUser } from "@/lib/auth";
import { listLeaveTypes } from "@/lib/leave-rules";

export default async function NewLeaveRulePage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let leaveTypes;
  let typesError = "";
  try {
    leaveTypes = await listLeaveTypes();
  } catch {
    typesError = "Unable to load leave types. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/leave-rules"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to leave rules
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">New rule</h2>
        <p className="text-text-secondary">
          Define how a leave type can be taken, effective from a chosen date.
          A future-effective rule joins the current one without changing it.
        </p>
      </div>

      {typesError && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {typesError}
        </div>
      )}

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <LeaveRuleForm leaveTypes={leaveTypes?.results ?? []} />
      </div>
    </div>
  );
}