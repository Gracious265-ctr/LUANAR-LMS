"use client";

import { ArrowLeft, Check, CheckCircle2, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CancellationDetailPanel } from "@/components/cancellations/cancellation-detail-panel";
import { ApprovedDocumentCard } from "@/components/documents/approved-document-card";
import { approvalVerb } from "@/lib/approvals/labels";
import { fetchApproval } from "@/lib/approvals/service";
import { Button } from "@/components/ui/button";
import type {
  ApprovalAction,
  ApprovalReview,
  DecisionBriefing,
} from "@/lib/approvals/types";

import { ApplicationDetailsCard } from "./application-details-card";
import { ApprovalHistoryTimeline } from "./approval-history-timeline";
import { BalanceCard } from "./balance-card";
import { StatusBadge } from "./badges";
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
  const [toast, setToast] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

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

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function handleSubmitted(briefing: DecisionBriefing) {
    setDialogKind(null);
    setToast(`Application ${approvalVerb(briefing.status)}`);
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
            href="/dashboard/approvals"
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
  const resubmission = app.submission_cycle > 1;

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24 lg:pb-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link
          href="/dashboard/approvals"
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
          <ApprovalHistoryTimeline data={data} />
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
              onClick={() => setDialogKind("approve")}
            />
            <MobileDecisionButton
              kind="reject"
              icon={<X className="h-4 w-4" aria-hidden="true" />}
              label="Reject"
              onClick={() => setDialogKind("reject")}
            />
            <MobileDecisionButton
              kind="return_for_correction"
              icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
              label="Return"
              onClick={() => setDialogKind("return_for_correction")}
            />
          </div>
        </div>
      )}

      <DecisionDialog
        kind={dialogKind}
        data={data}
        onClose={() => setDialogKind(null)}
        onSubmitted={handleSubmitted}
        onReloadRequest={retry}
      />

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-surface-card px-4 py-2.5 text-sm font-medium text-text-primary shadow-lg"
        >
          <CheckCircle2 className="h-4 w-4 text-status-approved" aria-hidden="true" />
          {toast}
        </div>
      )}
    </div>
  );
}

function MobileDecisionButton({
  kind,
  icon,
  label,
  onClick,
}: {
  kind: ApprovalAction;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  const className =
    kind === "approve"
      ? "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-transparent bg-button-primary px-3 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
      : kind === "reject"
        ? "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-status-rejected bg-status-rejected-subtle px-3 py-2 text-sm font-medium text-status-rejected"
        : "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-status-correction bg-status-correction-subtle px-3 py-2 text-sm font-medium text-status-correction";
  return (
    <Button type="button" onClick={onClick} className={className}>
      {icon}
      {label}
    </Button>
  );
}