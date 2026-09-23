import { Clock, Minus, RotateCcw, Check, X } from "lucide-react";

import { formatDateTime } from "@/lib/approvals/format";
import { ACTION_META } from "@/lib/approvals/labels";
import type { ApprovalReview, ApprovalStage } from "@/lib/approvals/types";
import { cn } from "@/lib/utils";

import { Panel } from "./panel";

const STATE_MARKER: Record<
  ApprovalStage["status"],
  { icon: typeof Clock; markerClass: string; iconClass: string }
> = {
  approved: { icon: Check, markerClass: "bg-status-approved text-white", iconClass: "text-white" },
  pending: {
    icon: Clock,
    markerClass: "border-2 border-status-pending bg-surface-card",
    iconClass: "text-status-pending",
  },
  rejected: { icon: X, markerClass: "bg-status-rejected text-white", iconClass: "text-white" },
  correction_requested: {
    icon: RotateCcw,
    markerClass: "bg-status-correction text-white",
    iconClass: "text-white",
  },
  waiting: {
    icon: Minus,
    markerClass: "border-2 border-border-strong bg-surface-card",
    iconClass: "text-text-muted",
  },
};

export function ApprovalHistoryTimeline({ data }: { data: ApprovalReview }) {
  const stages = data.workflow.stages;
  if (stages.length === 0) {
    return (
      <Panel title="Approval history">
        <p className="text-sm text-text-secondary">No approvals have been recorded yet.</p>
      </Panel>
    );
  }

  return (
    <Panel title="Approval history">
      <ol className="space-y-0">
        {stages.map((stage, index) => {
          const marker = STATE_MARKER[stage.status];
          const Icon = marker.icon;
          const isLast = index === stages.length - 1;
          const meta =
            stage.status === "approved"
              ? ACTION_META.approve
              : stage.status === "rejected"
                ? ACTION_META.reject
                : stage.status === "correction_requested"
                  ? ACTION_META.return_for_correction
                  : null;
          return (
            <li key={stage.order} className={cn("relative", !isLast && "pb-6")}>
              {!isLast && (
                <span
                  aria-hidden="true"
                  className="absolute left-[13px] top-7 h-[calc(100%-14px)] w-px bg-border-strong"
                />
              )}
              <div className="flex gap-3">
                <span
                  className={cn(
                    "relative z-10 grid size-7 shrink-0 place-content-center rounded-full",
                    marker.markerClass
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5", marker.iconClass)} aria-hidden="true" />
                </span>
                <div className="min-w-0 pt-0.5">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-sm font-semibold text-text-primary">
                      {stage.role_label}
                    </span>
                    {meta ? (
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          meta.badgeClass
                        )}
                      >
                        {meta.label}
                      </span>
                    ) : stage.status === "pending" ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-status-pending-subtle px-2.5 py-0.5 text-xs font-semibold text-status-pending">
                        Awaiting your decision
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted">
                        Not yet reached
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-text-muted">
                    {stage.status === "approved" || stage.status === "rejected" || stage.status === "correction_requested"
                      ? `${stage.assigned_approver} · ${formatDateTime(stage.decided_at) || "—"}`
                      : stage.status === "pending"
                        ? `Assigned to ${stage.assigned_approver}`
                        : stage.assigned_approver}
                  </p>
                  {meta && (
                    <p className="mt-1 text-sm text-text-secondary">
                      {stage.comment || "No comment"}
                    </p>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}