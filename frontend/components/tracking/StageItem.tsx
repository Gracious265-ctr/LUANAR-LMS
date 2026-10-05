import { Check, Clock, Minus, RotateCcw, X } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import type { TrackingStage, TrackingStatus } from "@/lib/tracking/types";
import { Badge } from "@/components/ui/badge";

const STATE_MARKER: Record<
  TrackingStage["state"],
  { icon: typeof Clock; markerClass: string; iconClass: string }
> = {
  approved: {
    icon: Check,
    markerClass: "bg-status-approved text-status-approved-on",
    iconClass: "text-status-approved-on",
  },
  awaiting: {
    icon: Clock,
    markerClass: "border-2 border-status-pending bg-surface-card",
    iconClass: "text-status-pending",
  },
  rejected: {
    icon: X,
    markerClass: "bg-status-rejected text-status-rejected-on",
    iconClass: "text-status-rejected-on",
  },
  returned: {
    icon: RotateCcw,
    markerClass: "bg-status-correction text-status-correction-on",
    iconClass: "text-status-correction-on",
  },
  skipped: {
    icon: Minus,
    markerClass: "border-2 border-border-strong bg-surface-muted",
    iconClass: "text-text-muted",
  },
  upcoming: {
    icon: Check,
    markerClass: "border-2 border-border-strong bg-surface-card",
    iconClass: "text-transparent",
  },
};

export function StageItem({
  stage,
  workflowStatus,
  connectorDashed,
}: {
  stage: TrackingStage;
  workflowStatus: TrackingStatus;
  connectorDashed: boolean;
}) {
  const marker = STATE_MARKER[stage.state];
  const MarkerIcon = marker.icon;
  const isUpcoming = stage.state === "upcoming";

  return (
    <li
      aria-current={stage.state === "awaiting" ? "step" : undefined}
      className={cn(isUpcoming && "opacity-60")}
    >
      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <span
            aria-hidden="true"
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-full",
              marker.markerClass
            )}
          >
            <MarkerIcon className={cn("h-4 w-4", marker.iconClass)} />
          </span>
          <span
            aria-hidden="true"
            className={cn(
              "my-1 w-0.5 flex-1 min-h-6",
              connectorDashed ? "border-l-2 border-dashed border-border-strong" : "bg-border-strong"
            )}
          />
        </div>

        <div className="pb-4 min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <p className="text-xs font-medium text-text-muted">
              Stage {stage.order}
            </p>
            <h3 className="font-semibold text-text-primary">
              {stage.role_label}
            </h3>
            <p className="text-sm text-text-muted">{metaLine(stage)}</p>
          </div>

          {stage.approver && (
            <div className="mt-1">
              <p className="text-sm text-text-secondary break-words">
                {stage.approver.name}
                <span className="text-text-muted">
                  {" "}
                  · {stage.approver.designation}
                </span>
              </p>
              {stage.approver.is_delegate && stage.approver.on_behalf_of && (
                <Badge
                  size="xs"
                  tone="neutral"
                  className="mt-1 font-medium"
                >
                  Acting for {stage.approver.on_behalf_of}
                </Badge>
              )}
            </div>
          )}

          {stage.comment && (
            <blockquote
              className={cn(
                "mt-2 rounded-r-lg border-l-2 px-3 py-2 text-sm break-words whitespace-pre-line",
                stage.state === "rejected" &&
                  "border-status-rejected bg-status-rejected-subtle text-status-rejected",
                stage.state === "returned" &&
                  "border-status-correction bg-status-correction-subtle text-status-correction",
                stage.state === "approved" &&
                  "border-border-strong bg-surface-subtle text-text-secondary",
                (stage.state === "awaiting" || stage.state === "upcoming") &&
                  "border-border-strong bg-surface-subtle text-text-secondary"
              )}
            >
              {stage.state === "rejected" && (
                <span className="mr-1 font-semibold">Reason:</span>
              )}
              {stage.state === "returned" && (
                <span className="mr-1 font-semibold">
                  Correction requested:
                </span>
              )}
              {stage.comment}
            </blockquote>
          )}

          {stage.state === "skipped" && (
            <p className="mt-1 text-sm text-text-secondary break-words">
              <span className="font-medium">Why skipped:</span>{" "}
              {stage.skip_reason ??
                "This stage was not needed for your application."}
            </p>
          )}

          {workflowStatus === "rejected" && stage.state === "rejected" && (
            <p className="mt-2 text-sm text-text-muted">
              Workflow stopped.
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

const META_LINE: Record<
  TrackingStage["state"],
  (stage: TrackingStage) => string
> = {
  approved: (stage) => `Approved ${formatDateTime(stage.decided_at)}`,
  awaiting: (stage) =>
    `Awaiting decision · assigned ${formatDateTime(stage.assigned_at)}`,
  rejected: (stage) => `Rejected ${formatDateTime(stage.decided_at)}`,
  returned: (stage) => `Returned for correction ${formatDateTime(stage.decided_at)}`,
  skipped: () => "Skipped",
  upcoming: () => "Not yet reached",
};

function metaLine(stage: TrackingStage): string {
  return META_LINE[stage.state](stage);
}