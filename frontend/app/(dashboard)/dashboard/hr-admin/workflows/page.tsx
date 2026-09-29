import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { WorkflowTable } from "@/components/hr/workflow-table";
import { getCurrentUser } from "@/lib/auth";
import { listWorkflows } from "@/lib/workflows";
import { Card } from "@/components/ui/card";

export default async function WorkflowsPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let workflows;
  let workflowsError = "";
  try {
    workflows = await listWorkflows();
  } catch {
    workflowsError = "Unable to load workflows. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Workflows</h2>
          <p className="text-text-secondary">
            Define the approval sequence applied to leave applications by
            employee category and department. Every stage is mandatory and
            executes in order.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/workflows/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New workflow
        </Link>
      </div>

      <Card>
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          All workflows
        </h3>
        {workflowsError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {workflowsError}
          </div>
        ) : workflows ? (
          <WorkflowTable workflows={workflows.results} />
        ) : null}
      </Card>
    </div>
  );
}