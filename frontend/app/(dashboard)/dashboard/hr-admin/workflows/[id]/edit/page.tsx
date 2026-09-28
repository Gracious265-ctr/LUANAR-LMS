import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { WorkflowForm } from "@/components/hr/workflow-form";
import { listApproverRoles } from "@/lib/approver-roles";
import type { ApproverRole } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import { getWorkflow } from "@/lib/workflows";

const ROLES_ERROR =
  "Unable to load approver roles, so a stage cannot be given an approver. Reload the page, or add a role under HR Administration → Roles.";

export default async function EditWorkflowPage({
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

  let workflow;
  try {
    workflow = await getWorkflow(id);
  } catch {
    notFound();
  }

  // Active roles only: a retired role cannot be added to a chain, but a stage
  // that already uses one still has to render, which the form handles.
  let roles: ApproverRole[] = [];
  let rolesError = "";
  try {
    roles = await listApproverRoles();
  } catch {
    rolesError = ROLES_ERROR;
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
          Edit workflow
        </h2>
        <p className="text-text-secondary">
          {workflow.name}. Reorder, add, or remove stages; the sequence is
          saved when you submit.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <WorkflowForm
          workflow={workflow}
          roles={roles}
          rolesError={rolesError}
        />
      </div>
    </div>
  );
}
