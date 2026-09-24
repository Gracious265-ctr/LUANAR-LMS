"use client";

import { Ban, ChevronRight, History } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatFinancialYear } from "@/lib/cancellation/format";
import { useCancellations } from "@/lib/cancellation/hooks";
import {
  NOTIFICATION_LABEL,
  REQUEST_STATUS_BADGE,
  REQUEST_STATUS_LABEL,
} from "@/lib/cancellation/labels";
import type { CancellationRequestSummary } from "@/lib/cancellation/types";
import { formatDateTime } from "@/lib/tracking/format";
import { Card } from "../approvals/primitives";
import { CancellationStageStepper } from "./CancellationStageStepper";

function StatusBadge({ status }: { status: CancellationRequestSummary["status"] }) {
  const label =
    status === "approved"
      ? "Cancelled"
      : REQUEST_STATUS_LABEL[status];
  const badge =
    status === "approved"
      ? "bg-status-cancelled-subtle text-status-cancelled"
      : REQUEST_STATUS_BADGE[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
        badge
      )}
    >
      <Ban className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}

/**
 * Cancellation card for the employee tracking page. Rendered only when at
 * least one cancellation request exists (it fetches the owner-scoped list,
 * newest first). Shows the latest request with its stage stepper, outcome
 * banner (restored days / rejected outcome), notification chip, and a
 * collapsible history of earlier requests.
 */
export function CancellationCard({
  applicationId,
  refreshSignal,
}: {
  applicationId: string;
  refreshSignal?: unknown;
}) {
  const { state } = useCancellations(applicationId, refreshSignal);

  if (state.status === "loading" || state.status === "error") return null;
  if (state.data.length === 0) return null;

  const [latest, ...older] = state.data;
  return (
    <Card title="Leave cancellation" icon={<History className="h-4 w-4" />}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusBadge status={latest.status} />
        <span className="text-xs text-text-muted">
          Requested {formatDateTime(latest.requested_at)}
        </span>
      </div>

      <div className="mt-4 space-y-2">
        <p className="text-sm text-text-secondary">Your reason</p>
        <p className="rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-primary">
          {latest.reason}
        </p>
      </div>

      {latest.stages.length > 0 && (
        <CancellationStageStepper stages={latest.stages} className="mt-5" />
      )}

      {latest.status === "approved" && (
        <OutcomeBanner
          days={latest.balance_restored_days}
          financialYear={latest.restored_financial_year}
        />
      )}
      {latest.status === "rejected" && (
        <RejectionBanner latest={latest} />
      )}

      <p className="mt-4 border-t border-border-default pt-3 text-xs text-text-muted">
        Outcome notification:{" "}
        {NOTIFICATION_LABEL[latest.employee_notification_state]}
      </p>

      {older.length > 0 && <CancellationHistory older={older} />}
    </Card>
  );
}

function OutcomeBanner({
  days,
  financialYear,
}: {
  days: string;
  financialYear: string | null;
}) {
  const restored = Number(days) > 0;
  return (
    <div className="mt-5 rounded-xl border border-status-approved/30 bg-status-approved-subtle p-4">
      <p className="font-medium text-status-approved">Leave cancelled.</p>
      <p className="mt-1 text-sm text-text-secondary">
        {restored
          ? `${days} annual leave ${Number(days) === 1 ? "day" : "days"} restored to ${formatFinancialYear(financialYear)} balance.`
          : "No annual leave balance was affected."}
      </p>
    </div>
  );
}

function RejectionBanner({ latest }: { latest: CancellationRequestSummary }) {
  const rejecting = [...latest.stages]
    .sort((a, b) => a.order - b.order)
    .find((stage) => stage.status === "rejected");
  return (
    <div className="mt-5 rounded-xl border border-status-rejected/30 bg-status-rejected-subtle p-4">
      <p className="font-medium text-status-rejected">
        Your leave remains approved.
      </p>
      {rejecting?.comment && (
        <p className="mt-1 text-sm break-words whitespace-pre-line text-text-secondary">
          {rejecting.role_label}: “{rejecting.comment}”
        </p>
      )}
    </div>
  );
}

function CancellationHistory({
  older,
}: {
  older: CancellationRequestSummary[];
}) {
  return (
    <details className="group mt-5 border-t border-border-default pt-3">
      <summary className="flex cursor-pointer list-none items-center gap-1 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90"
          aria-hidden="true"
        />
        Cancellation history ({older.length})
      </summary>
      <ul className="mt-3 space-y-4">
        {older.map((request) => (
          <li
            key={request.id}
            className="rounded-lg border border-border-default p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-text-primary">
                {REQUEST_STATUS_LABEL[request.status]}
              </p>
              <p className="text-xs text-text-muted">
                {formatDateTime(request.requested_at)}
              </p>
            </div>
            {request.status === "rejected" && <RejectionBanner latest={request} />}
            {request.stages.length > 0 && (
              <CancellationStageStepper stages={request.stages} className="mt-4" />
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}