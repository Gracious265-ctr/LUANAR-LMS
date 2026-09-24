import { formatDateTime } from "@/lib/cancellations/format";
import { STAGE_STATE_META } from "@/lib/cancellations/labels";
import type { CancellationStage } from "@/lib/cancellations/types";
import { cn } from "@/lib/utils";

/**
 * Compact vertical stepper for a cancellation request's two Reviewer/HOD stages.
 * The pending stage is highlighted; decided stages show their comment.
 */
export function CancellationStageStepper({
  stages,
}: {
  stages: CancellationStage[];
}) {
  if (stages.length === 0) return null;
  return (
    <ol
      aria-label="Cancellation approval progress"
      className="space-y-0"
    >
      {stages.map((stage, index) => (
        <li key={stage.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <StageDot stage={stage} />
            {index < stages.length - 1 && (
              <div className="w-px flex-1 bg-border-default" aria-hidden="true" />
            )}
          </div>
          <div className={cn("pb-4", index === stages.length - 1 && "pb-0")}>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <p className="text-sm font-medium text-text-primary">
                {stage.role_label}
              </p>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  STAGE_STATE_META[stage.status].badgeClass
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    STAGE_STATE_META[stage.status].dotClass
                  )}
                  aria-hidden="true"
                />
                {STAGE_STATE_META[stage.status].label}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-text-secondary">{stage.approver_name}</p>
            {stage.decided_at && (
              <p className="mt-0.5 text-xs text-text-muted">
                Decided {formatDateTime(stage.decided_at)}
              </p>
            )}
            {stage.comment && (
              <p className="mt-1 max-w-md text-sm text-text-secondary">
                “{stage.comment}”
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function StageDot({ stage }: { stage: CancellationStage }) {
  const meta = STAGE_STATE_META[stage.status];
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-1 flex h-4 w-4 items-center justify-center rounded-full border-2",
        stage.status === "approved" || stage.status === "rejected"
          ? "border-border-default bg-surface-muted"
          : stage.status === "pending"
            ? "border-brand-primary bg-brand-primary-subtle"
            : "border-border-default bg-surface-card"
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          stage.status === "approved" || stage.status === "rejected"
            ? meta.dotClass
            : stage.status === "pending"
              ? "bg-brand-primary"
              : "bg-text-muted"
        )}
      />
    </span>
  );
}