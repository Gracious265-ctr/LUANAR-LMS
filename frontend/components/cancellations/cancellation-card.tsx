"use client";

import { CheckCircle2, ChevronDown, History, XCircle } from "lucide-react";
import { useState } from "react";

import { formatDateTime } from "@/lib/cancellations/format";
import {
  KIND_LABELS,
  NOTIFICATION_STATE_LABELS,
  REQUEST_STATUS_META,
  outcomeBanner,
} from "@/lib/cancellations/labels";
import type { CancellationRequest } from "@/lib/cancellations/types";
import { cn } from "@/lib/utils";

import { CancellationStageStepper } from "./cancellation-stage-stepper";

/**
 * The employee-visible cancellation card. Only rendered when at least one
 * request exists; the latest request is shown in full and earlier rejected
 * requests collapse behind a "Cancellation history" toggle.
 */
export function CancellationCard({
  requests,
}: {
  requests: CancellationRequest[];
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const latest = requests[0];
  const earlier = requests.slice(1);
  const meta = REQUEST_STATUS_META[latest.status];
  const Icon = meta.icon;
  const banner = outcomeBanner(
    latest.status,
    latest.balance_restored_days,
    latest.restored_financial_year
  );
  const rejectingComment =
    latest.status === "rejected"
      ? latest.stages.find((stage) => stage.status === "rejected")?.comment ?? null
      : null;

  return (
    <section
      aria-label="Cancellation request"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-text-primary">
            {KIND_LABELS[latest.kind]}
          </h2>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
              meta.badgeClass
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {meta.label}
          </span>
        </div>
        <span className={cn("text-xs", meta.textClass)}>
          <span className="text-text-muted">Notification: </span>
          {NOTIFICATION_STATE_LABELS[latest.employee_notification_state]}
        </span>
      </div>

      {banner && (
        <div
          className={cn(
            "mt-4 rounded-lg p-3 text-sm",
            latest.status === "approved"
              ? "bg-status-approved-subtle text-status-approved"
              : "bg-status-rejected-subtle text-status-rejected"
          )}
        >
          {banner}
          {rejectingComment && (
            <p className="mt-1 text-text-secondary">
              Reason given: “{rejectingComment}”
            </p>
          )}
        </div>
      )}

      <div className="mt-4 grid gap-6 md:grid-cols-2">
        <div className="min-w-0">
          <h3 className="mb-3 text-sm font-medium text-text-secondary">Approval progress</h3>
          <CancellationStageStepper stages={latest.stages} />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-text-secondary">Your reason</h3>
          <p className="mt-1 whitespace-pre-wrap text-sm text-text-primary">
            {latest.reason}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            Requested{" "}
            <time dateTime={latest.requested_at ?? undefined}>
              {formatDateTime(latest.requested_at)}
            </time>
          </p>
        </div>
      </div>

      {earlier.length > 0 && (
        <div className="mt-4 border-t border-border-default pt-3">
          <button
            type="button"
            onClick={() => setHistoryOpen((open) => !open)}
            aria-expanded={historyOpen}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary hover:underline"
          >
            <History className="h-4 w-4" aria-hidden="true" />
            Cancellation history ({earlier.length})
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform",
                historyOpen && "rotate-180"
              )}
              aria-hidden="true"
            />
          </button>
          {historyOpen && (
            <ul className="mt-3 space-y-2">
              {earlier.map((request) => (
                <li
                  key={request.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-surface-muted px-3 py-2 text-sm"
                >
                  <span className="font-medium text-text-primary">
                    {KIND_LABELS[request.kind]}
                  </span>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      REQUEST_STATUS_META[request.status].badgeClass
                    )}
                  >
                    {request.status === "rejected" ? (
                      <XCircle className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                    )}
                    {REQUEST_STATUS_META[request.status].label}
                  </span>
                  <span className="text-xs text-text-muted">
                    Requested {formatDateTime(request.requested_at)}
                    {request.decided_at &&
                      ` · Decided ${formatDateTime(request.decided_at)}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}