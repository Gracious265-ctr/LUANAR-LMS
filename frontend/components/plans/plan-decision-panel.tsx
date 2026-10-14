"use client";

import { Check, X } from "lucide-react";

import { formatDateTime } from "@/lib/plans/format";
import { restrictionLabel } from "@/lib/plans/labels";
import type { PlanAction, PlanApprovalDetail, PlanStage } from "@/lib/plans/types";
import { Button } from "@/components/ui/button";

export interface PlanDecisionPanelProps {
  data: PlanApprovalDetail;
  onAction: (kind: PlanAction) => void;
}

/**
 * The approve/reject controls, or the reason they are unavailable.
 *
 * Every branch renders something: a disabled pair of buttons would read as a
 * broken page, so when the backend says `can_decide` is false this names the
 * restriction it reported instead.
 */
export function PlanDecisionPanel({
  data,
  onAction,
}: PlanDecisionPanelProps) {
  if (data.my_decision) {
    return (
      <p className="text-sm text-text-secondary">
        You {pastTense(data.my_decision.action)} this plan
        {data.my_decision.decided_at
          ? ` on ${formatDateTime(data.my_decision.decided_at)}`
          : ""}
        .
      </p>
    );
  }

  if (!data.can_decide) {
    return (
      <p className="max-w-sm text-sm text-text-secondary">
        {restrictionLabel(
          "not_current_stage",
          data.stages.find((stage) => stage.status === "pending")?.role_label ?? null,
          data.meta.status
        )}
      </p>
    );
  }

  const pendingStage: PlanStage | undefined = data.stages.find(
    (stage) => stage.status === "pending"
  );

  return (
    <div className="flex items-center gap-2">
      <Button variant="primary" onClick={() => onAction("approve")}>
        <Check className="h-4 w-4" aria-hidden="true" />
        Approve
      </Button>
      <Button
        variant="secondary"
        onClick={() => onAction("reject")}
        className="border-status-rejected bg-status-rejected-subtle text-status-rejected"
      >
        <X className="h-4 w-4" aria-hidden="true" />
        Reject
      </Button>
      {pendingStage?.is_final && (
        <span className="text-xs text-text-muted">Final stage</span>
      )}
    </div>
  );
}

function pastTense(action: PlanAction): string {
  return action === "approve" ? "approved" : "rejected";
}
