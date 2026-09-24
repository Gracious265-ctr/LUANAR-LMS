"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

import { CancellationDecisionPanel } from "@/components/cancellation/CancellationDecisionPanel";
import { useCapabilities } from "@/lib/approvals/capabilities-context";
import { decisionPastTense, formatDateTime } from "@/lib/approvals/format";
import { useApprovalDetail } from "@/lib/approvals/hooks";
import type { ApprovalDetail, DecisionAction } from "@/lib/approvals/types";

import { StatusBadge } from "../tracking/StatusBadge";
import { ApplicationDetailsCard } from "./application-details-card";
import { ApprovalHistoryTimeline } from "./approval-history-timeline";
import { BalanceCard } from "./balance-card";
import { DecisionPanel } from "./decision-panel";
import { DocumentsCard } from "./documents-card";
import { EmployeeInfoCard } from "./employee-info-card";
import { LeaveHistoryCard } from "./leave-history-card";
import { ResubmissionBadge } from "./primitives";

export function ApprovalReview({
  applicationId,
  cancellationRequestId,
}: {
  applicationId: string;
  cancellationRequestId?: string;
}) {
  const { state, setState, refetch } = useApprovalDetail(applicationId);
  const { refresh: refreshCapabilities } = useCapabilities();
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  function onDecisionApplied(updated: ApprovalDetail, action: DecisionAction) {
    setState({ status: "ok", data: updated });
    setToast(`Decision saved — you ${decisionPastTense(action)} ${updated.reference}.`);
    void refreshCapabilities();
  }

  if (state.status === "loading") {
    return <ReviewSkeleton />;
  }

  if (state.status === "not_found") {
    return (
      <NotFoundCard
        title="Application not found"
        message="This application may have been withdrawn, or the link is out of date."
      />
    );
  }

  if (state.status === "error") {
    return <NotFoundCard title="Something went wrong" message={state.message} />;
  }

  const detail = state.data;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <Link
          href="/approvals"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to queue
        </Link>
      </div>

      <header className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs tracking-wide text-text-muted uppercase">
            Review
          </p>
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold text-text-primary">
            {detail.reference}
            <ResubmissionBadge cycle={detail.submission_cycle} />
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {detail.employee.full_name} ·{" "}
            {formatDateTime(detail.application.submitted_at)}
          </p>
        </div>
        <StatusBadge status={detail.status} />
      </header>

      {cancellationRequestId && (
        <CancellationDecisionPanel
          requestId={cancellationRequestId}
          onRefetch={() => {
            refetch();
            void refreshCapabilities();
          }}
        />
      )}

      <div className="flex flex-col gap-6 lg:flex-row-reverse">
        <div className="space-y-6 lg:w-[340px] lg:shrink-0">
          <DecisionPanel
            detail={detail}
            onDecisionApplied={onDecisionApplied}
            onConflict={refetch}
            onForbidden={refetch}
          />
          <EmployeeInfoCard detail={detail} />
          <BalanceCard detail={detail} />
        </div>

        <div className="min-w-0 flex-1 space-y-6">
          <ApplicationDetailsCard detail={detail} />
          <DocumentsCard detail={detail} />
          <ApprovalHistoryTimeline detail={detail} />
          <LeaveHistoryCard detail={detail} />
        </div>
      </div>

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-status-approved px-4 py-3 text-sm font-semibold text-white shadow-lg"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          {toast}
        </div>
      )}
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div aria-busy="true" className="space-y-6 pb-24 lg:pb-0">
      <div className="h-4 w-24 animate-pulse rounded bg-surface-muted" />
      <div className="h-8 w-64 animate-pulse rounded bg-surface-muted" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px] lg:flex-row-reverse">
        <div className="order-2 space-y-6">
          <div className="h-48 animate-pulse rounded-xl bg-surface-muted" />
          <div className="h-48 animate-pulse rounded-xl bg-surface-muted" />
        </div>
        <div className="order-1 space-y-6">
          <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
          <div className="h-96 animate-pulse rounded-xl bg-surface-muted" />
        </div>
      </div>
    </div>
  );
}

function NotFoundCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
      <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-secondary">
        {message}
      </p>
      <Link
        href="/approvals"
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to approvals
      </Link>
    </div>
  );
}