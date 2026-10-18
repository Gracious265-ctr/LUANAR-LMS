"use client";

import { AlertTriangle, Check, Scale, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Panel } from "@/components/approvals/panel";
import { formatDateTime } from "@/lib/cancellations/format";
import { formatDayCount } from "@/lib/cancellations/labels";
import {
  fetchCancellationDetail,
} from "@/lib/cancellations/service";
import type { CancellationDetail } from "@/lib/cancellations/types";
import { formatDate } from "@/lib/format";
import { STATUS_STYLES, STATUS_TEXT } from "@/lib/status-styles";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

import { stepsFromCancellation } from "@/lib/chain-steps";
import { Stepper } from "@/components/ui/Stepper";

import { CancellationDecisionDialog } from "./cancellation-decision-dialog";

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
  const [reloadKey, setReloadKey] = useState(0);
  const { showToast } = useToast();
  // The pre-decision detail, kept so a failed request can put the optimistic
  // update back exactly as it was (spec 3.5).
  const snapshotRef = useRef<CancellationDetail | null>(null);

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

  function handleOptimistic(comment: string) {
    snapshotRef.current = data;
    setData((prev) =>
      prev && dialogKind
        ? withOptimisticDecision(prev, dialogKind, comment)
        : prev
    );
  }

  function handleRollback(message: string) {
    if (snapshotRef.current) {
      setData(snapshotRef.current);
      snapshotRef.current = null;
    }
    showToast(message, "error");
  }

  function handleSubmitted(next: CancellationDetail) {
    setDialogKind(null);
    snapshotRef.current = null;
    setData(next);
    showToast(
      next.request.status === "approved"
        ? "Cancellation approved."
        : "Cancellation rejected.",
      next.request.status === "approved" ? "success" : "error"
    );
    onApplicationChanged?.();
  }

  function handleConflict() {
    if (snapshotRef.current) {
      setData(snapshotRef.current);
      snapshotRef.current = null;
    }
    showToast("This request changed. Refreshing…", "info");
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
            STATUS_TEXT[data.request.status]
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
            className={`flex items-start gap-2 rounded-lg p-3 text-sm ${STATUS_STYLES.pending}`}
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
            <div className="mt-2" role="group" aria-label="Cancellation approval progress">
              <Stepper
                steps={stepsFromCancellation(data.request.stages)}
                orientation="vertical"
              />
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
        onOptimistic={handleOptimistic}
        onRollback={handleRollback}
        onSubmitted={handleSubmitted}
        onConflict={handleConflict}
      />
    </Panel>
  );
}

/**
 * The panel state the moment the decision is dispatched: the stage records the
 * decision, the request settles, and the buttons flip to the "you decided"
 * view. The server response replaces this on success; rollback restores the
 * snapshot on failure, so this only ever lives between request and response.
 */
function withOptimisticDecision(
  detail: CancellationDetail,
  decision: "approve" | "reject",
  comment: string
): CancellationDetail {
  const decidedAt = new Date().toISOString();
  const status = decision === "approve" ? "approved" : "rejected";
  return {
    ...detail,
    can_decide: false,
    stage_version: detail.stage_version + 1,
    my_decision: {
      decision: status,
      decided_at: decidedAt,
      comment: comment || null,
    },
    request: {
      ...detail.request,
      status,
      decided_at: decidedAt,
      stage_version: detail.request.stage_version + 1,
      stages: detail.request.stages.map((stage) =>
        stage.status === "pending"
          ? { ...stage, status, decided_at: decidedAt, comment: comment || null }
          : stage
      ),
    },
  };
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
                  STATUS_TEXT[data.my_decision.decision]
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
      <Button
        type="button"
        disabled={data.leave_started}
        title={data.leave_started ? "Leave has started; this request can only be rejected." : undefined}
        onClick={onApprove}
        variant="primary"
        size="lg"
        className="w-full"
      >
        <Check className="h-4 w-4" aria-hidden="true" />
        Approve
      </Button>
      <Button
        type="button"
        onClick={onReject}
        variant="secondary"
        size="lg"
        className="w-full border-status-rejected bg-status-rejected-subtle text-status-rejected"
      >
        <XCircle className="h-4 w-4" aria-hidden="true" />
        Reject
      </Button>
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