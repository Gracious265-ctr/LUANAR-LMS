import {
  CheckCircle2,
  CircleDot,
  Clock,
  RotateCcw,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { decisionPastTense, formatDateTime } from "@/lib/approvals/format";
import type { ApprovalDetail, ApprovalStage, StageStatus } from "@/lib/approvals/types";

const STAGE_ACCENT: Record<StageStatus, string> = {
  waiting: "bg-surface-muted text-text-secondary",
  pending: "bg-status-pending-subtle text-status-pending",
  approved: "bg-status-approved-subtle text-status-approved",
  rejected: "bg-status-rejected-subtle text-status-rejected",
  correction_requested: "bg-status-correction-subtle text-status-correction",
};

function StageIcon({ status }: { status: StageStatus }) {
  const className = "h-4 w-4";
  switch (status) {
    case "approved":
      return <CheckCircle2 className={className} aria-hidden="true" />;
    case "rejected":
      return <XCircle className={className} aria-hidden="true" />;
    case "correction_requested":
      return <RotateCcw className={className} aria-hidden="true" />;
    case "pending":
      return <Clock className={className} aria-hidden="true" />;
    default:
      return <CircleDot className={className} aria-hidden="true" />;
  }
}

export function ApprovalHistoryTimeline({ detail }: { detail: ApprovalDetail }) {
  const { stages, current_stage } = detail;
  const pendingStageLabel =
    current_stage && detail.status === "pending"
      ? current_stage.role_label
      : null;

  return (
    <section
      aria-label="Approval history"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <h2 className="mb-4 text-base font-semibold text-text-primary">
        Approval history
      </h2>
      {stages.length === 0 ? (
        <p className="text-sm text-text-muted">
          No approval steps have been recorded for this application.
        </p>
      ) : (
        <ol className="space-y-5">
          {stages.map((stage) => (
            <ApprovalStageRow
              key={stage.order}
              stage={stage}
              awaitingLabel={
                stage.status === "pending" ? pendingStageLabel : null
              }
            />
          ))}
        </ol>
      )}
    </section>
  );
}

function ApprovalStageRow({
  stage,
  awaitingLabel,
}: {
  stage: ApprovalStage;
  awaitingLabel: string | null;
}) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          STAGE_ACCENT[stage.status]
        )}
      >
        <StageIcon status={stage.status} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-1">
          <p className="text-sm font-medium text-text-primary">
            {stage.role_label}
          </p>
          {stage.decided_at && (
            <time
              dateTime={stage.decided_at}
              className="text-xs text-text-muted"
            >
              {formatDateTime(stage.decided_at)}
            </time>
          )}
        </div>
        <p className="text-xs text-text-secondary">
          {stageActionText(stage)}
        </p>
        {stage.approver_name && (
          <p className="text-xs text-text-secondary">{stage.approver_name}</p>
        )}
        {awaitingLabel && (
          <p className="mt-1 text-xs font-medium text-status-pending">
            Awaiting your decision
          </p>
        )}
        {stage.comment && (
          <p className="mt-1 rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
            {stage.comment}
          </p>
        )}
      </div>
    </li>
  );
}

function stageActionText(stage: ApprovalStage): string {
  switch (stage.status) {
    case "pending":
      return "Decision required";
    case "waiting":
      return "Not yet reached";
    case "correction_requested":
      return "Returned for correction";
    case "approved":
    case "rejected":
      return stage.action
        ? `${stage.role_label} ${decisionPastTense(stage.action)}`
        : "Decided";
    default:
      return stage.status;
  }
}