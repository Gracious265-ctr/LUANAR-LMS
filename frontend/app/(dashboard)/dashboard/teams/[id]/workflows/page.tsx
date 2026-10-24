import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Plus } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
<<<<<<< HEAD
import { canAccessTeams } from "@/lib/nav/teams-nav";
=======
import { canConfigureChains } from "@/lib/team-access";
>>>>>>> features/team-base
import type { Team, WorkflowRef } from "@/lib/teams";
import { getTeam, listTeamWorkflows } from "@/lib/teams";

const WORKFLOWS_ERROR =
  "Unable to load this team's workflows, so the list may be incomplete.";

/**
 * Every chain a team owns.
 *
 * A team may own several — a replacement chain is built alongside the live one
 * — and all of them route at once, each carrying the employees who are members
 * of it. This is the screen that lists them and builds the next: the team form
 * creates a chain with the team, and this is where a second one is created for
 * a team that already exists.
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
<<<<<<< HEAD
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
=======
  const isHr = user.role === "hr";
  // HR creates teams and designates managers; the manager runs their own team's
  // chains. A manager reaches only their own team here — ``getTeam`` is scoped
  // to the teams they manage, so another team 404s before this renders.
  if (!isHr && user.manages_teams !== true) {
    redirect("/");
>>>>>>> features/team-base
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

  const canConfigure = canConfigureChains(isHr);

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
            <p className="text-text-secondary">
              The approval chains {team.name} owns. One of them routes — the
              rest are held ready, and switching between them is a recorded
              decision rather than an edit to whichever happens to be open.
            </p>
          </div>
          {canConfigure && (
            <Link
              href={`/dashboard/teams/${team.id}/workflows/new`}
              className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
            >
              <Plus className="h-4 w-4" />
              New workflow
            </Link>
          )}
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
          <p className="text-sm text-text-muted">
            None yet. A team routes nothing until it owns a chain with steps —
            build the first one, or add it when the team was created.
          </p>
        ) : (
          <ul className="divide-y divide-border-default">
            {workflows.map((workflow) => (
              <li
                key={workflow.id}
                className="flex flex-wrap items-center justify-between gap-2 py-3"
              >
                <div>
                  <Link
                    href={`/dashboard/teams/${team.id}/workflows/${workflow.id}`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {workflow.name}
                  </Link>
                  <p className="text-xs text-text-muted">
                    {workflow.section_count} step
                    {workflow.section_count === 1 ? "" : "s"}
                    {workflow.effective_from
                      ? ` · from ${workflow.effective_from}`
                      : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      workflow.is_active
                        ? "bg-brand-secondary-subtle text-brand-secondary"
                        : "bg-surface-muted text-text-muted"
                    }`}
                  >
                    {workflow.is_active ? "In force" : "Not in force"}
                  </span>
                  {canConfigure && (
                    <Link
                      href={`/dashboard/teams/${team.id}/workflows/${workflow.id}/edit`}
                      className="text-xs font-medium text-brand-primary hover:text-brand-primary-hover"
                    >
                      Edit steps
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
