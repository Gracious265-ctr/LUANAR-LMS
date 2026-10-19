import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { WorkflowRoutingActions } from "@/components/hr/workflow-routing-actions";
import { getCurrentUser } from "@/lib/auth";
import { canAccessOrganisation } from "@/lib/nav/organisation-nav";
import { getWorkflow, workflowStateLabel } from "@/lib/workflows";
import { getTeam, listTeamWorkflows } from "@/lib/teams";
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

  // A chain is read from the team that owns it: a chain belonging to another
  // team is not reachable here, because the steps on it decide applications
  // that are not this team's.
  if (workflow.team !== team.id) {
    notFound();
  }

  const workflows = await listTeamWorkflows(team.id).catch(() => []);

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

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="text-lg font-semibold text-text-primary">Steps</h3>
        <p className="mt-1 text-sm text-text-secondary">
          In order, from the first decision to the last. Resolution is what the
          backend would do today, not an instruction: an unstaffed step falls
          back to the next holding rather than guessing at a person.
        </p>
        {workflow.sections.length === 0 ? (
          <p className="mt-3 text-sm text-text-muted">
            No steps yet. A chain with no steps cannot be routed through, and
            the team cannot route applications while it owns only this.
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {workflow.sections.map((section) => (
              <li
                key={section.id}
                className="rounded-lg border border-border-default bg-surface-page p-4"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <span className="text-xs font-medium text-text-muted">
                      Step {section.order}
                    </span>
                    <h4 className="text-sm font-semibold text-text-primary">
                      {section.name}
                    </h4>
                    <p className="text-xs text-text-secondary">
                      {section.approver_role_label}
                    </p>
                  </div>
                  <span className="inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-secondary">
                    {section.resolution.label}
                    {section.resolution.user_name
                      ? ` — ${section.resolution.user_name}`
                      : ""}
                  </span>
                </div>
                <div className="mt-2 text-xs text-text-muted">
                  {section.memberships.filter((m) => m.is_effective).length > 0
                    ? section.memberships
                        .filter((m) => m.is_effective)
                        .map((m) => m.user_name)
                        .join(", ")
                    : "No member appointed on this step."}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-1 text-lg font-semibold text-text-primary">
          Which chain routes
        </h3>
        <p className="mb-3 text-sm text-text-secondary">
          {workflow.is_routing
            ? "This is the chain new applications go through."
            : "This chain is owned but not routing. Point the team at it when its steps are ready."}
        </p>
        <WorkflowRoutingActions team={team} workflows={workflows} />
      </div>
    </div>
  );
}
