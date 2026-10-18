import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { WorkflowForm } from "@/components/hr/workflow-form";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import type { Team } from "@/lib/teams";
import { getTeam } from "@/lib/teams";

const ROLES_ERROR =
  "Unable to load approver roles, so no step can be described.";

/**
 * A new chain for a team that already exists.
 *
 * The usual reason to be here is a replacement: the live chain is in force and
 * being edited would change the routing of applications already inside it, so
 * the new steps are built beside it and the team is pointed at them when they
 * are ready.
 */
export default async function NewWorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  // Building a chain is the team manager's job after the handover; HR creates
  // the team and designates the manager, and the standalone chain endpoint
  // refuses HR. A manager reaches only their own team: ``getTeam`` is scoped,
  // so a foreign team 404s before the form is reachable. HR is sent to the
  // team's chain list, where routing — HR's call — lives.
  if (user.manages_teams !== true) {
    redirect(user.role === "hr" ? `/organisation/teams/${id}/workflows` : "/");
  }

  let team: Team;
  try {
    team = await getTeam(id);
  } catch {
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
          href={`/organisation/teams/${team.id}/workflows`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to workflows
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          New workflow for {team.name}
        </h2>
        <p className="text-text-secondary">
          Describe the steps in order. The chain is created owned by this team
          and routes nothing until you point the team at it — so a chain being
          built never changes who is approving today.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <WorkflowForm team={team} roles={roles} rolesError={rolesError} />
      </div>
    </div>
  );
}
