import Link from "next/link";
import { Pencil, Users } from "lucide-react";

import type { WorkflowRef } from "@/lib/teams";
import { RouteChainButton } from "@/components/hr/workflow-routing-actions";
import { buttonVariants } from "@/components/ui/button";

interface WorkflowCompactCardProps {
  workflow: WorkflowRef;
  teamId: number;
  /** Only the team's designated manager may make a chain its default. */
  canMakeDefault?: boolean;
}

export function WorkflowCompactCard({
  workflow,
  teamId,
  canMakeDefault = true,
}: WorkflowCompactCardProps) {
  const steps = workflow.section_count;
  const effective = workflow.effective_from ?? "—";
  const routing = workflow.is_routing ? "Default" : "Additional";

  return (
    <div
      className="rounded-lg border border-border-default bg-surface-page p-4"
      aria-label={`${workflow.name}, ${routing} chain`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <Link
            href={`/dashboard/teams/${teamId}/workflows/${workflow.id}`}
            className="font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            {workflow.name}
          </Link>
          <p className="text-xs text-text-muted">
            {steps} step{steps === 1 ? "" : "s"}
            {effective !== "—" ? ` · from ${effective}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Link
            href={`/dashboard/teams/${teamId}/workflows/${workflow.id}#members`}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <Users className="h-3.5 w-3.5" />
            View members
          </Link>
          {canMakeDefault && (
            <Link
              href={`/dashboard/teams/${teamId}/workflows/${workflow.id}/edit`}
              className={buttonVariants({ variant: "secondary", size: "sm" })}
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </Link>
          )}
          <RouteChainButton
            teamId={teamId}
            workflow={workflow}
            canManage={canMakeDefault}
          />
        </div>
      </div>
    </div>
  );
}
