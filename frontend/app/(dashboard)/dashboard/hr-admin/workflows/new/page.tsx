import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { WorkflowForm } from "@/components/hr/workflow-form";
import { getCurrentUser } from "@/lib/auth";

export default async function NewWorkflowPage() {
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
          href="/dashboard/hr-admin/workflows"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to workflows
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          New workflow
        </h2>
        <p className="text-text-secondary">
          Build the approval sequence for a category or department. The first
          stage runs first, then each following stage in order.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <WorkflowForm />
      </div>
    </div>
  );
}