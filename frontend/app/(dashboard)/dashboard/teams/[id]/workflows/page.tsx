import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Plus } from "lucide-react";

import { WorkflowCompactCard } from "@/components/hr/workflow-compact-card";
import { getCurrentUser } from "@/lib/auth";
import { canAccessTeams } from "@/lib/nav/teams-nav";
import type { Team, WorkflowRef } from "@/lib/teams";
import { getTeam, listTeamWorkflows } from "@/lib/teams";
import { buttonVariants } from "@/components/ui/button";

const WORKFLOWS_ERROR =
  "Unable to load this team's workflows, so the list may be incomplete.";

/**
 * Every chain a team owns, and which one is its default.
 *
 * A team routes all of them at the same time — each employee goes through the
 * chain they are enrolled on — so "default" is where the unenrolled route, not
 * the only chain in force. This screen lists them, marks the default, and
 * builds the next: the team form creates a chain with the team, and this is
 * where a second one is created for a team that already exists. The routing
 * starts once the chain has steps and its members are enrolled.
 */
export default async function TeamWorkflowsPage({
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

  let workflows: WorkflowRef[] = [];
  let error = "";
  try {
    workflows = await listTeamWorkflows(team.id);
  } catch {
    error = WORKFLOWS_ERROR;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/teams/${team.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {team.name}
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-text-primary">
              Workflows
            </h2>
            <p className="text-text-secondary">The approval chains {team.name} owns.</p>
          </div>
          <Link
            href={`/dashboard/teams/${team.id}/workflows/new`}
            className={buttonVariants({ variant: "primary" })}
          >
            <Plus className="h-4 w-4" />
            New workflow
          </Link>
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-3 text-lg font-semibold text-text-primary">
          Chains
        </h3>
        {workflows.length === 0 ? (
          <p className="text-sm text-text-muted">None yet.</p>
        ) : (
          <ul className="space-y-3">
            {workflows.map((workflow) => (
              <li key={workflow.id}>
                <WorkflowCompactCard
                  workflow={workflow}
                  teamId={team.id}
                  canMakeDefault={team.is_team_manager}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
