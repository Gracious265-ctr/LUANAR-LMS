"use client";

import { AlertTriangle, Check, CheckCircle2, Scale, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Panel } from "@/components/approvals/panel";
import { formatDateTime } from "@/lib/cancellations/format";
import { formatDayCount } from "@/lib/cancellations/labels";
import {
  fetchCancellationDetail,
} from "@/lib/cancellations/service";
import type { CancellationDetail } from "@/lib/cancellations/types";
import { formatDate } from "@/lib/tracking/format";
import { cn } from "@/lib/utils";

import { CancellationDecisionDialog } from "./cancellation-decision-dialog";
import { CancellationStageStepper } from "./cancellation-stage-stepper";

export interface CancellationDetailPanelProps {
  requestId: string;
  onApplicationChanged?: () => void;
}

/**
 * The cancellation request panel shown at the top of the Unit 16 review page
 * when ``/approvals/[applicationId]?cancellation={requestId}`` resolves to a
 * request the viewer is assigned to. Renders nothing when it does not resolve.
 */
export function CancellationDetailPanel({
  requestId,
  onApplicationChanged,
}: CancellationDetailPanelProps) {
  const [data, setData] = useState<CancellationDetail | null>(null);
  const [dialogKind, setDialogKind] = useState<"approve" | "reject" | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchCancellationDetail(requestId)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
        } else {
          setData(null);
        }
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [requestId, reloadKey]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  function handleSubmitted(next: CancellationDetail) {
    setDialogKind(null);
    setData(next);
    setToast(
      next.request.status === "approved"
        ? "Cancellation approved."
        : "Cancellation rejected."
    );
    onApplicationChanged?.();
  }

  function handleConflict() {
    setToast("This request changed. Refreshing…");
    setReloadKey((value) => value + 1);
  }

  if (!data) return null;

  const app = data.application;
  const balanceDays = data.balance_impact.restore_days;
  const hasBalanceImpact = Number(balanceDays) > 0;

  return (
    <Panel
      title="Cancellation request"
      action={
        <span
          className={cn(
            "text-xs font-semibold",
            data.request.status === "approved"
              ? "text-status-approved"
              : data.request.status === "rejected"
                ? "text-status-rejected"
                : "text-status-pending"
          )}
        >
          {data.request.status === "pending" ? "Pending approval" : data.request.status}
        </span>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="text-sm font-medium text-text-secondary">Requested by</h3>
            <p className="mt-1 text-sm text-text-primary">{data.requested_by_name}</p>
            <p className="mt-0.5 text-xs text-text-muted">
              <time dateTime={data.request.requested_at ?? undefined}>
                {formatDateTime(data.request.requested_at)}
              </time>
            </p>
          </div>
          <div>
            <h3 className="text-sm font-medium text-text-secondary">Employee&apos;s reason</h3>
            <p className="mt-1 whitespace-pre-wrap text-sm text-text-primary">
              {data.request.reason}
            </p>
          </div>
        </div>

        {data.leave_started && (
          <div
            role="note"
            className="flex items-start gap-2 rounded-lg bg-status-pending-subtle p-3 text-sm text-status-pending"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>Leave has started; this request can only be rejected.</p>
          </div>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-sm font-medium text-text-secondary">Original leave</h3>
            <dl className="mt-2 divide-y divide-border-default border-t border-border-default text-sm">
              <Row label="Reference">
                <span className="font-mono">{app.reference}</span>
              </Row>
              <Row label="Leave type">{app.leave_type.name || "—"}</Row>
              <Row label="Dates">
                {formatDate(app.start_date) || "—"} → {formatDate(app.end_date) || "—"}
              </Row>
              <Row label="Days">
                {app.working_days} working · {app.calendar_days} calendar
              </Row>
              <Row label="Financial year">{app.financial_year_label || "—"}</Row>
            </dl>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-text-muted" aria-hidden="true" />
              <h3 className="text-sm font-medium text-text-secondary">Balance impact</h3>
            </div>
            <p className="mt-2 text-sm text-text-primary">
              {hasBalanceImpact ? (
                <>
                  Approving restores{" "}
                  <span className="font-semibold">
                    {formatDayCount(balanceDays)} day{Number(balanceDays) === 1 ? "" : "s"}
                  </span>{" "}
                  to FY {data.balance_impact.restore_financial_year ?? "—"} balance.
                </>
              ) : (
                "No annual leave balance impact."
              )}
            </p>
            <h3 className="mt-4 text-sm font-medium text-text-secondary">Approval progress</h3>
            <div className="mt-2">
              <CancellationStageStepper stages={data.request.stages} />
            </div>
          </div>
        </div>

        <CancellationDecisionSection
          data={data}
          onApprove={() => setDialogKind("approve")}
          onReject={() => setDialogKind("reject")}
        />
      </div>

      <CancellationDecisionDialog
        kind={dialogKind}
        data={data}
        onClose={() => setDialogKind(null)}
        onSubmitted={handleSubmitted}
        onConflict={handleConflict}
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
    </Panel>
  );
}

function CancellationDecisionSection({
  data,
  onApprove,
  onReject,
}: {
  data: CancellationDetail;
  onApprove: () => void;
  onReject: () => void;
}) {
  if (!data.can_decide) {
    return (
      <div className="rounded-lg border border-border-default bg-surface-muted p-3">
        <p className="text-sm text-text-secondary">
          {data.my_decision ? (
            <>
              You{" "}
              <span
                className={cn(
                  "font-semibold",
                  data.my_decision.decision === "approved"
                    ? "text-status-approved"
                    : "text-status-rejected"
                )}
              >
                {decisionVerb(data.my_decision.decision)}
              </span>{" "}
              this cancellation on {formatDateTime(data.my_decision.decided_at)}.
            </>
          ) : (
            "This cancellation is not with you right now."
          )}
        </p>
        {data.my_decision?.comment && (
          <p className="mt-1 text-sm text-text-secondary">“{data.my_decision.comment}”</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <button
        type="button"
        disabled={data.leave_started}
        title={data.leave_started ? "Leave has started; this request can only be rejected." : undefined}
        onClick={onApprove}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[#009119] px-4 py-2.5 font-medium text-white hover:bg-[#008017] focus:outline-none focus:ring-2 focus:ring-[#009119]/40 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Check className="h-4 w-4" aria-hidden="true" />
        Approve
      </button>
      <button
        type="button"
        onClick={onReject}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-status-rejected bg-status-rejected-subtle px-4 py-2.5 font-medium text-status-rejected hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-status-rejected/40"
      >
        <XCircle className="h-4 w-4" aria-hidden="true" />
        Reject
      </button>
    </div>
  );
}

function decisionVerb(decision: "approved" | "rejected"): string {
  return decision === "approved" ? "approved" : "rejected";
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-3 py-2">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="col-span-2 break-words text-text-primary">{children}</dd>
    </div>
  );
}