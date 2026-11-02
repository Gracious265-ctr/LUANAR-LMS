import type { Step, StepStatus } from "@/components/ui/Stepper";
import type { ApprovalStage, StageStatus } from "@/lib/approvals/types";
import type { CancellationStage } from "@/lib/cancellations/types";
import type {
  StageState,
  TrackingApprover,
  TrackingResponse,
} from "@/lib/tracking/types";
import { formatDateTime } from "@/lib/tracking/format";

/**
 * Adapters from each real payload shape into the generic `Step[]` the Stepper
 * consumes (refinement 02 §3). The component stays domain-free; everything
 * that knows about a leave chain or a cancellation chain lives here.
 */

function joinContext(parts: Array<string | null | undefined>): string | undefined {
  const kept = parts.filter((part): part is string => Boolean(part));
  return kept.length > 0 ? kept.join(" · ") : undefined;
}

/** Approval-chain context (role designation, acting-for) folded into a sublabel. */
function approverContext(approver: TrackingApprover | null): string[] {
  if (!approver) return [];
  return [
    approver.designation,
    approver.is_delegate && approver.on_behalf_of
      ? `Acting for ${approver.on_behalf_of}`
      : null,
  ].filter((part): part is string => Boolean(part));
}

const TRACKING_STATUS: Record<StageState, StepStatus> = {
  approved: "completed",
  rejected: "error",
  awaiting: "current",
  upcoming: "pending",
  skipped: "skipped",
};

export function chainFromTracking(data: TrackingResponse): Step[] {
  return data.stages.map((stage): Step => {
    const approver = stage.approver;
    const vacant = stage.state === "awaiting" && !approver;
    const status: StepStatus = vacant ? "blocked" : TRACKING_STATUS[stage.state];
    const context = approverContext(approver);

    let sublabel: string | undefined;
    if (vacant) sublabel = "No approver assigned";
    else if (stage.state === "rejected")
      sublabel = joinContext(["Rejected", ...context]);
    else if (stage.state === "skipped")
      sublabel = stage.skip_reason ?? "Skipped";
    else if (stage.state === "awaiting")
      sublabel = joinContext([
        ...context,
        stage.assigned_at ? `Assigned ${formatDateTime(stage.assigned_at)}` : null,
      ]);
    else sublabel = joinContext(context);

    return {
      id: `stage-${stage.order}`,
      label: stage.role_label,
      sublabel,
      status,
      actor: approver ? { id: approver.name, name: approver.name } : null,
      timestamp: stage.decided_at,
      detail: stage.comment,
      isActing: approver?.is_delegate ?? false,
    };
  });
}

const WORKFLOW_STATUS: Record<StageStatus, StepStatus> = {
  approved: "completed",
  rejected: "error",
  pending: "current",
  waiting: "pending",
  skipped: "skipped",
};

export function chainFromWorkflow(stages: ApprovalStage[]): Step[] {
  return stages.map((stage): Step => {
    const assigned =
      (stage as any).approver ||
      (stage as any).assigned_approver ||
      (stage as any).acting_for ||
      null;
    const vacant = stage.status === "pending" && !assigned;
    const status: StepStatus = vacant ? "blocked" : WORKFLOW_STATUS[stage.status];

    let sublabel: string | undefined;
    if (vacant) sublabel = "No approver assigned";
    else if (stage.status === "rejected") sublabel = "Rejected";
    else if (stage.status === "skipped")
      sublabel = (stage as any).skip_reason ?? "Skipped";
    else if (stage.status === "pending" && stage.assigned_at)
      sublabel = `Assigned ${formatDateTime(stage.assigned_at)}`;

    return {
      id: `stage-${stage.order}`,
      label: stage.role_label,
      sublabel,
      status,
      actor: assigned ? { id: assigned, name: assigned } : null,
      timestamp: stage.decided_at,
      detail: stage.comment,
      isActing: !!(stage as any).acting_for,
    };
  });
}

const CANCELLATION_STATUS: Record<CancellationStage["status"], StepStatus> = {
  approved: "completed",
  rejected: "error",
  pending: "current",
  waiting: "pending",
  not_reached: "pending",
};

/**
 * A cancellation request walks a subset of the original approval chain, so it
 * reuses the same component with a shorter `Step[]` (refinement 02 §3.4).
 */
export function stepsFromCancellation(stages: CancellationStage[]): Step[] {
  return stages.map((stage): Step => {
    const name = stage.approver_name?.trim();
    return {
      id: stage.id,
      label: stage.role_label,
      sublabel: stage.status === "rejected" ? "Rejected" : undefined,
      status: CANCELLATION_STATUS[stage.status],
      actor: name ? { id: name, name } : null,
      timestamp: stage.decided_at,
      detail: stage.comment,
      isActing: false,
    };
  });
}
