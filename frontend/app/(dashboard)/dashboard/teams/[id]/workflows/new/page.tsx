import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { WorkflowForm } from "@/components/hr/workflow-form";
import type { ApproverRole } from "@/lib/approver-roles";
import {
  listApproverRoles,
  listEligibleApproverRoles,
} from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import {
  canAccessTeams,
  isTeamsAdministrator,
} from "@/lib/nav/teams-nav";
import type { Team } from "@/lib/teams";
import { getTeam } from "@/lib/teams";

const ROLES_ERROR =
  "Unable to load approver roles, so no step can be described.";

/**
 * A new chain for a team that already exists.
 *
 * A team routes every chain its people are enrolled on, so a second chain is
 * how part of a team's staff gets different approval steps — not a switch that
 * stops the first one. Building it here leaves the existing chain and the
 * applications inside it untouched; enrol the people who should use it when
 * its steps are ready.
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
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
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
    // HR reads the whole role list; a manager may not reach that HR-only
    // endpoint, so they read the read-only list a team's manager is allowed —
    // otherwise the form opens with no roles and cannot describe a step.
    roles = isTeamsAdministrator(user)
      ? await listApproverRoles()
      : await listEligibleApproverRoles();
  } catch {
    rolesError = ROLES_ERROR;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/teams/${team.id}/workflows`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to workflows
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          New workflow for {team.name}
        </h2>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <WorkflowForm team={team} roles={roles} rolesError={rolesError} />
      </div>
    </div>
  );
}
