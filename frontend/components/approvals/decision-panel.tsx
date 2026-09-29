"use client";

import { Check, RotateCcw, X } from "lucide-react";

import { STATUS_META, restrictionLabel } from "@/lib/approvals/labels";
import { formatDateTime } from "@/lib/approvals/format";
import type { ApprovalAction, ApprovalReview } from "@/lib/approvals/types";
import { Button } from "@/components/ui/button";

import { Panel } from "./panel";

export interface DecisionPanelProps {
  data: ApprovalReview;
  onAction: (kind: ApprovalAction) => void;
  disabled?: boolean;
}

export function DecisionPanel({ data, onAction, disabled }: DecisionPanelProps) {
  if (!data.can_decide) {
    return (
      <Panel title="Decision">
        <p className="text-sm text-text-secondary">
          {restrictionLabel(
            data.decision_restriction,
            data.workflow.current_stage?.role_label ?? null,
            data.workflow.state
          )}
        </p>
        {data.my_decision && data.workflow.state !== "pending" && (
          <p className="mt-2 text-xs text-text-muted">
            You {decisionPastTense(data.my_decision.action)} this application on{" "}
            {formatDateTime(data.my_decision.decided_at)}.
          </p>
        )}
        {statusNote(data.workflow.state) && (
          <p className="mt-2 text-xs text-text-muted">{statusNote(data.workflow.state)}</p>
        )}
      </Panel>
    );
  }

  return (
    <Panel title="Decision">
      <div className="space-y-2.5">
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("approve")}
          variant="primary"
          size="lg"
          className="w-full bg-[#009119] text-white hover:bg-[#008017] border border-transparent"
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          Approve
        </Button>
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("reject")}
          variant="secondary"
          size="lg"
          className="w-full border-status-rejected bg-status-rejected-subtle text-status-rejected"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Reject
        </Button>
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("return_for_correction")}
          variant="secondary"
          size="lg"
          className="w-full border-status-correction bg-status-correction-subtle text-status-correction"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Return for Correction
        </Button>
      </div>
    </Panel>
  );
}

function decisionPastTense(action: ApprovalAction): string {
  switch (action) {
    case "approve":
      return "approved";
    case "reject":
      return "rejected";
    case "return_for_correction":
      return "returned for correction";
  }
}

function statusNote(status: ApprovalReview["workflow"]["state"]): string | null {
  if (status === "cancelled") {
    return `Status: ${STATUS_META.cancelled.label.toLowerCase()}.`;
  }
  if (status === "rejected") {
    return "The workflow has stopped for this application.";
  }
  return null;
}