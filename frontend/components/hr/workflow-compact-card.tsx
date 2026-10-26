import Link from "next/link";

import type { WorkflowRef } from "@/lib/teams";

interface WorkflowCompactCardProps {
  workflow: WorkflowRef;
  teamId: number;
  readOnly?: boolean;
}

export function WorkflowCompactCard({
  workflow,
  teamId,
  readOnly = false,
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
        <div className="space-y-1">
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
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
              workflow.is_routing
                ? "bg-brand-secondary-subtle text-brand-secondary"
                : "bg-surface-muted text-text-muted"
            }`}
          >
            {routing}
          </span>
          {readOnly && (
            <span className="text-xs text-text-muted">
              <svg
                className="inline h-3 w-3 mr-1 shrink-0"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              Read only
            </span>
          )}
          {!readOnly && (
            <Link
              href={`/dashboard/teams/${teamId}/workflows/${workflow.id}/edit`}
              className="text-xs font-medium text-brand-primary hover:text-brand-primary-hover"
            >
              Edit steps
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
