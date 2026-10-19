"use client";

import { ArrowLeft, Check, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { CancellationDetailPanel } from "@/components/cancellations/cancellation-detail-panel";
import { ApprovedDocumentCard } from "@/components/documents/approved-document-card";
import { approvalVerb } from "@/lib/approvals/labels";
import { fetchApproval } from "@/lib/approvals/service";
import { chainFromWorkflow } from "@/lib/chain-steps";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import type {
  ApprovalAction,
  ApprovalReview,
  ApprovalStatus,
  CurrentStageBlock,
  DecisionBriefing,
  StageStatus,
} from "@/lib/approvals/types";

import { ApplicationDetailsCard } from "./application-details-card";
import { BalanceCard } from "./balance-card";
import { StatusBadge } from "./badges";
import { Stepper } from "@/components/ui/Stepper";
import { DecisionDialog } from "./decision-dialog";
import { DecisionPanel } from "./decision-panel";
import { DocumentsCard } from "./documents-card";
import { EmployeeInfoCard } from "./employee-info-card";
import { LeaveHistoryCard } from "./leave-history-card";
import { Panel } from "./panel";
import { Badge } from "@/components/ui/badge";

export function ApprovalDetail({
  id,
  cancellationRequestId,
}: {
  id: string;
  cancellationRequestId?: string;
}) {
  const [data, setData] = useState<ApprovalReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [dialogKind, setDialogKind] = useState<ApprovalAction | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const { showToast } = useToast();
  // The pre-decision page, kept so a failed request can put the optimistic
  // update back exactly as it was (spec 3.5).
  const decisionSnapshotRef = useRef<ApprovalReview | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApproval(id)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
          setNotFound(false);
          setError("");
        } else if (result.kind === "not_found") {
          setNotFound(true);
          setError("");
        } else {
          setError(result.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  // The optimistic patch runs the moment the dialog dispatches the request,
  // so the stepper and the decision panel move before the round trip finishes.
  function handleOptimistic(comment: string) {
    decisionSnapshotRef.current = data;
    setData((prev) =>
      prev && dialogKind ? withOptimisticDecision(prev, dialogKind, comment) : prev
    );
  }

  function handleRollback(message: string) {
    if (decisionSnapshotRef.current) {
      setData(decisionSnapshotRef.current);
      decisionSnapshotRef.current = null;
    }
    showToast(message, "error");
  }

  function handleSubmitted(briefing: DecisionBriefing) {
    setDialogKind(null);
    decisionSnapshotRef.current = null;
    showToast(
      `Application ${approvalVerb(briefing.status)}`,
      briefing.status === "rejected" ? "error" : "success"
    );
    setReloadKey((value) => value + 1);
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl">
        <Panel title="Application not found">
          <p className="text-sm text-text-secondary">
            This application is not available to you, or it no longer exists.
          </p>
          <Link
            href="/approvals"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to approvals
          </Link>
        </Panel>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Panel title="Something went wrong">
          <p className="text-sm text-status-rejected">{error}</p>
          <Button type="button" onClick={retry} variant="primary" className="mt-4">
            Retry
          </Button>
        </Panel>
      </div>
    );
  }

  if (loading || !data || data.application.id !== id) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="h-6 w-1/3 animate-pulse rounded bg-surface-muted" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="h-72 animate-pulse rounded-xl border border-border-default bg-surface-card lg:col-span-2" />
          <div className="h-72 animate-pulse rounded-xl border border-border-default bg-surface-card" />
        </div>
      </div>
    );
  }

  const app = data.application;
  const chainSteps = chainFromWorkflow(data.workflow.stages);
  const resubmission = app.submission_cycle > 1;

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24 lg:pb-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link
          href="/approvals"
          className="inline-flex items-center gap-1 font-medium text-brand-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Approvals
        </Link>
        <span className="text-text-muted">›</span>
        <span className="font-medium text-text-primary">{app.reference}</span>
        <StatusBadge status={data.workflow.state} />
        {resubmission && (
          <Badge
            size="sm"
            tone="neutral"
            className="font-medium"
          >
            Resubmission #{app.submission_cycle}
          </Badge>
        )}
      </div>

      <h1 className="text-xl font-mono font-semibold tracking-tight text-text-primary">{app.reference}</h1>

      {cancellationRequestId && (
        <CancellationDetailPanel
          requestId={cancellationRequestId}
          onApplicationChanged={retry}
        />
      )}

      <div className="relative grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <ApplicationDetailsCard data={data} />
          <DocumentsCard data={data} />
          {/* An approver reviewing a finalized application can read the same
              official document the employee sees. */}
          {data.workflow.state === "approved" && (
            <ApprovedDocumentCard applicationId={id} />
          )}
          <Panel title="Approval history">
            {chainSteps.length > 0 ? (
              <Stepper steps={chainSteps} />
            ) : (
              <p className="text-sm text-text-secondary">
                No approvals have been recorded yet.
              </p>
            )}
          </Panel>
          <LeaveHistoryCard data={data} />
        </div>

        <div className="space-y-6 self-start lg:sticky lg:top-6">
          <DecisionPanel
            data={data}
            disabled={dialogKind !== null}
            onAction={setDialogKind}
          />
          <EmployeeInfoCard data={data} />
          <BalanceCard data={data} />
        </div>
      </div>

      {data.can_decide && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border-default bg-surface-card p-3 shadow-lg lg:hidden">
          <div className="mx-auto flex max-w-5xl items-center gap-2">
            <MobileDecisionButton
              kind="approve"
              icon={<Check className="h-4 w-4" aria-hidden="true" />}
              label="Approve"
              disabled={dialogKind !== null}
              onClick={() => setDialogKind("approve")}
            />
            <MobileDecisionButton
              kind="reject"
              icon={<X className="h-4 w-4" aria-hidden="true" />}
              label="Reject"
              disabled={dialogKind !== null}
              onClick={() => setDialogKind("reject")}
            />
          </div>
        </div>
      )}

      <DecisionDialog
        kind={dialogKind}
        data={data}
        onClose={() => setDialogKind(null)}
        onOptimistic={handleOptimistic}
        onRollback={handleRollback}
        onSubmitted={handleSubmitted}
        onReloadRequest={retry}
      />
    </div>
  );
}

function MobileDecisionButton({
  kind,
  icon,
  label,
  disabled,
  onClick,
}: {
  kind: ApprovalAction;
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const className =
    kind === "approve"
      ? "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-transparent bg-button-primary px-3 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
      : "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-status-rejected bg-status-rejected-subtle px-3 py-2 text-sm font-medium text-status-rejected";
  return (
    <Button type="button" onClick={onClick} disabled={disabled} className={className}>
      {icon}
      {label}
    </Button>
  );
}

/**
 * The page state the moment a decision is dispatched: the pending stage
 * records the decision, the workflow advances (or settles when the decision is
 * terminal), and the panel flips to "already decided". The server response
 * replaces this on success; the dialog's rollback restores the snapshot on
 * failure, so this only ever lives between request and response.
 */
function withOptimisticDecision(
  data: ApprovalReview,
  action: ApprovalAction,
  comment: string
): ApprovalReview {
  const decidedAt = new Date().toISOString();
  const isFinal = data.workflow.current_stage?.is_final ?? false;
  const stageStatus: StageStatus = action === "approve" ? "approved" : "rejected";
  const terminal = action === "reject" || isFinal;
  const state: ApprovalStatus = terminal
    ? action === "reject"
      ? "rejected"
      : "approved"
    : data.workflow.state;

  let stages = data.workflow.stages.map((stage) =>
    stage.status === "pending"
      ? {
          ...stage,
          status: stageStatus,
          decided_at: decidedAt,
          comment: comment || null,
        }
      : stage
  );

  let currentStage: CurrentStageBlock | null = null;
  if (!terminal) {
    const waiting = stages
      .filter((stage) => stage.status === "waiting")
      .sort((a, b) => a.order - b.order);
    const [next, ...rest] = waiting;
    if (next) {
      stages = stages.map((stage) =>
        stage.order === next.order
          ? { ...stage, status: "pending" as StageStatus }
          : stage
      );
      currentStage = {
        order: next.order,
        role: next.role,
        role_label: next.role_label,
        is_final: rest.length === 0,
        next_role_label: rest[0]?.role_label ?? null,
      };
    }
  }

  return {
    ...data,
    can_decide: false,
    decision_restriction: "already_decided",
    my_decision: {
      action,
      role_label: data.workflow.current_stage?.role_label ?? "",
      comment: comment || null,
      decided_at: decidedAt,
    },
    workflow: {
      ...data.workflow,
      state,
      current_stage: currentStage,
      stages,
      current_decision: {
        action,
        role_label: data.workflow.current_stage?.role_label ?? "",
        comment: comment || null,
        decided_at: decidedAt,
      },
    },
  };
}