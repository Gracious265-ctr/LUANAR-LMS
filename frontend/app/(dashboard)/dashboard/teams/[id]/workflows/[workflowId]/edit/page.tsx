import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { WorkflowForm } from "@/components/hr/workflow-form";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import { canAccessOrganisation } from "@/lib/nav/organisation-nav";
import { getWorkflow } from "@/lib/workflows";
import { getTeam } from "@/lib/teams";

const ROLES_ERROR =
  "Unable to load approver roles, so no step can be described.";

/**
 * Edit the steps of a chain this team owns.
 *
 * The steps are sent as the whole ordered list, so what is saved is exactly
 * what was described. A chain that belongs to another team is not reachable
 * from here — the URL is the owning team's — because the steps on it decide
 * applications that are not this team's.
 */
export default async function EditWorkflowPage({
  params,
}: {
  params: Promise<{ id: string; workflowId: string }>;
}) {
  const { id, workflowId } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!canAccessOrganisation(user)) {
    redirect("/dashboard");
  }

  let team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  let workflow;
  try {
    workflow = await getWorkflow(workflowId);
  } catch {
    notFound();
  }
  if (workflow.team !== team.id) {
    notFound();
  }

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
          href={`/dashboard/teams/${team.id}/workflows/${workflow.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {workflow.name}
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          Edit steps
        </h2>
        <p className="text-text-secondary">
          {workflow.name} · {team.name}
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <WorkflowForm
          workflow={workflow}
          team={team}
          roles={roles}
          rolesError={rolesError}
        />
      </div>
    </div>
  );
}
