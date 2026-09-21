import type { TrackingResponse } from "@/lib/tracking/types";

import { StageItem } from "./StageItem";

/**
 * Renders ``stages`` in the received (ascending) order. An ordered list with
 * exactly one `aria-current="step"` on the awaiting stage.
 */
export function ApprovalStepper({ data }: { data: TrackingResponse }) {
  const stages = data.stages;

  return (
    <section
      aria-label="Approval progress"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <h2 className="mb-4 text-base font-semibold text-text-primary">
        Approval progress
      </h2>
      <ol className="space-y-0">
        {stages.map((stage, index) => (
          <StageItem
            key={stage.order}
            stage={stage}
            workflowStatus={data.status}
            connectorDashed={
              stages[index + 1]
                ? stages[index + 1].state === "upcoming"
                : false
            }
          />
        ))}
        {stages.length === 0 && (
          <li className="text-sm text-text-muted">No workflow stages.</li>
        )}
      </ol>
    </section>
  );
}