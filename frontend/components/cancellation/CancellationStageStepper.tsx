import { Check, Clock, X } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import type { CancellationStage } from "@/lib/cancellation/types";

function StateHint({ stage }: { stage: CancellationStage }) {
  switch (stage.status) {
    case "waiting":
      return <span className="text-xs text-text-muted">Not yet reached</span>;
    case "pending":
      return (
        <span className="flex items-center gap-1 text-xs font-medium text-status-pending">
          <Clock className="h-3 w-3" aria-hidden="true" />
          Awaiting decision
        </span>
      );
    case "approved":
      return <span className="text-xs font-medium text-status-approved">Approved</span>;
    case "rejected":
      return <span className="text-xs font-medium text-status-rejected">Rejected</span>;
    case "not_reached":
      return <span className="text-xs text-text-muted">Not reached</span>;
    default:
      return null;
  }
}

function StateIcon({ stage }: { stage: CancellationStage }) {
  if (stage.status === "approved") {
    return (
      <span
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-status-approved-subtle text-status-approved"
        aria-hidden="true"
      >
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (stage.status === "rejected") {
    return (
      <span
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-status-rejected-subtle text-status-rejected"
        aria-hidden="true"
      >
        <X className="h-3.5 w-3.5" />
      </span>
    );
  }
  return (
    <span
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
        stage.status === "pending"
          ? "bg-status-pending-subtle text-status-pending"
          : "bg-surface-muted text-text-muted"
      )}
      aria-hidden="true"
    >
      <Clock className="h-3.5 w-3.5" />
    </span>
  );
}

/**
 * Compact vertical stepper for cancellation approval stages. Shows role,
 * approver, state, decision time and comment per stage. ``aria-current`` marks
 * the single pending stage for screen readers.
 */
export function CancellationStageStepper({
  stages,
  className,
}: {
  stages: CancellationStage[];
  className?: string;
}) {
  const ordered = [...stages].sort((a, b) => a.order - b.order);
  return (
    <ol
      aria-label="Cancellation progress"
      className={cn("space-y-4", className)}
    >
      {ordered.map((stage) => {
        const isCurrent = stage.status === "pending";
        return (
          <li
            key={stage.order}
            aria-current={isCurrent ? "step" : undefined}
            className="flex items-start gap-3"
          >
            <StateIcon stage={stage} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <p className="text-sm font-medium text-text-primary">
                  {stage.role_label}
                </p>
                <StateHint stage={stage} />
              </div>
              {stage.approver_name && (
                <p className="text-xs text-text-secondary">
                  {stage.approver_name}
                </p>
              )}
              {stage.decided_at && (
                <time
                  dateTime={stage.decided_at}
                  className="text-xs text-text-muted"
                >
                  {formatDateTime(stage.decided_at)}
                </time>
              )}
              {stage.comment && (
                <p className="mt-1 rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
                  {stage.comment}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}