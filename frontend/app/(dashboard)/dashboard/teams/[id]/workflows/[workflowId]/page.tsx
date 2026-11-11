import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { WorkflowMemberTable } from "@/components/hr/workflow-member-table";
import { getCurrentUser } from "@/lib/auth";
import { canAccessTeams } from "@/lib/nav/teams-nav";
import { getWorkflow, workflowStateLabel } from "@/lib/workflows";
import { getTeam } from "@/lib/teams";
import { buttonVariants } from "@/components/ui/button";

/**
 * One chain: its steps, in order, and how each one finds the person who acts.
 *
 * "How it resolves" is the point of reading a chain on its own. A step may be
 * staffed by hand, or it may fall back to a team-wide, campus-wide or
 * institution-wide holding — and which of those applies is what tells HR
 * whether this chain can be put into force, and where to go to staff it.
 */
export default async function WorkflowDetailPage({
  params,
}: {
  params: Promise<{ id: string; workflowId: string }>;
}) {
  const { id, workflowId } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!canAccessTeams(user)) {
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

  // A chain is read from the team that owns it: a chain belonging to another
  // team is not reachable here, because the steps on it decide applications
  // that are not this team's.
  if (workflow.team !== team.id) {
    notFound();
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
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-bold text-text-primary">
                {workflow.name}
              </h2>
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  workflow.is_routing
                    ? "bg-brand-secondary-subtle text-brand-secondary"
                    : "bg-surface-muted text-text-muted"
                }`}
              >
                {workflowStateLabel(workflow.state)}
              </span>
            </div>
            <p className="text-text-secondary">
              Owned by {team.name}
              {workflow.effective_from
                ? ` · from ${workflow.effective_from}`
                : ""}
            </p>
          </div>
          <Link
            href={`/dashboard/teams/${team.id}/workflows/${workflow.id}/edit`}
            className={buttonVariants({ variant: "secondary" })}
          >
            <Pencil className="h-4 w-4" />
            Edit steps
          </Link>
        </div>
      </div>

      <div className="rounded-lg border border-border-default bg-surface-card p-4">
        <h3 className="text-sm font-semibold text-text-primary">Steps</h3>
        {workflow.sections.length === 0 ? (
          <p className="mt-2 text-xs text-text-muted">No steps yet.</p>
        ) : (
          <dl className="mt-3 space-y-2">
            {workflow.sections.map((section) => {
              const approver = section.approver;
              const approver_name = section.approver_name;
              return (              <div
                key={section.id}
                className="rounded border border-border-default bg-surface-page p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <dt className="text-xs font-medium text-text-muted">
                      Step {section.order}
                    </dt>
                    <dd className="text-sm font-semibold text-text-primary truncate">
                      {section.name}
                    </dd>
                    <dd className="text-xs text-text-secondary truncate">
                      {section.approver_role_label}
                    </dd>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-muted px-2 py-0.5 text-xs font-medium text-text-secondary">
                    {section.resolution.label}
                    {section.resolution.user_name
                      ? ` — ${section.resolution.user_name}`
                      : ""}
                    {approver && approver_name && !section.resolution.user_name
                      ? ` — ${approver_name}`
                      : ""}
                  </span>
                </div>
              </div>
              );
            })}
          </dl>
        )}
      </div>

      <div
        id="members"
        className="scroll-mt-24 rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">Members</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Team members enrolled on this chain. Each one routes their leave
              through it.
            </p>
          </div>
          <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-secondary">
            {workflow.members.length} member
            {workflow.members.length === 1 ? "" : "s"}
          </span>
        </div>

        {workflow.members.length === 0 ? (
          <p className="mt-3 rounded-md border border-dashed border-border-default p-3 text-sm text-text-muted">
            No members yet. A team manager can add them from Edit steps.
          </p>
        ) : (
          <WorkflowMemberTable members={workflow.members} />
        )}
      </div>
    </div>
  );
}
