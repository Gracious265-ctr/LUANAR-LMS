import Link from "next/link";
import { Pencil } from "lucide-react";

import type { WorkflowRef } from "@/lib/teams";
import { RouteChainButton } from "@/components/hr/workflow-routing-actions";
import { buttonVariants } from "@/components/ui/button";

interface WorkflowCompactCardProps {
  workflow: WorkflowRef;
  teamId: number;
}

export function WorkflowCompactCard({
  workflow,
  teamId,
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
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
              workflow.is_routing
                ? "bg-brand-secondary-subtle text-brand-secondary"
                : "bg-surface-muted text-text-muted"
            }`}
          >
            {routing}
          </span>
          <Link
            href={`/dashboard/teams/${teamId}/workflows/${workflow.id}/edit`}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Link>
          {!workflow.is_routing && (
            <RouteChainButton teamId={teamId} workflow={workflow} />
          )}
        </div>
      </div>
    </div>
  );
}
