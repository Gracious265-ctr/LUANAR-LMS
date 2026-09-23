import Link from "next/link";
import { AlertCircle, CornerUpLeft } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import type { TrackingResponse } from "@/lib/tracking/types";

/**
 * Attention panel: rejection or correction details with the (optional)
 * "Edit & resubmit" action. Rendered only while ``rejection`` or ``correction``
 * is non-null.
 */
export function OutcomePanel({ data }: { data: TrackingResponse }) {
  const outcome =
    data.status === "rejected" ? data.rejection : data.correction;
  if (!outcome) return null;

  const isRejected = data.status === "rejected";
  const accent = isRejected
    ? "border-status-rejected bg-status-rejected-subtle text-status-rejected"
    : "border-status-correction bg-status-correction-subtle text-status-correction";

  const resubmission = data.resubmission;

  return (
    <section
      aria-label={isRejected ? "Rejection details" : "Correction details"}
      className={cn(
        "rounded-xl border bg-surface-card p-5 shadow-subtle",
        isRejected ? "border-status-rejected/30" : "border-status-correction/30"
      )}
    >
      <div className={cn("flex items-center gap-2", isRejected ? "text-status-rejected" : "text-status-correction")}>
        {isRejected ? (
          <AlertCircle className="h-5 w-5" aria-hidden="true" />
        ) : (
          <CornerUpLeft className="h-5 w-5" aria-hidden="true" />
        )}
        <h2 className="text-base font-semibold text-text-primary">
          {isRejected ? "Rejection details" : "Correction details"}
        </h2>
      </div>

      <dl className="mt-4 space-y-3 text-sm">
        <div>
          <dt className="text-xs font-medium text-text-muted">Stage</dt>
          <dd className="break-words text-text-primary">
            Stage {outcome.stage_order} · {outcome.role_label}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">Approver</dt>
          <dd className="break-words text-text-primary">
            {outcome.approver_name}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">Decision</dt>
          <dd className="text-text-primary">
            <time dateTime={outcome.decided_at}>
              {formatDateTime(outcome.decided_at)}
            </time>
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">
            {isRejected ? "Reason" : "Comment"}
          </dt>
          <dd
            className={cn(
              "mt-1 rounded-lg border-l-2 px-3 py-2 break-words whitespace-pre-line",
              accent
            )}
          >
            {outcome.reason ?? outcome.comment}
          </dd>
        </div>
      </dl>

      {resubmission.returns_to_stage && (
        <p className="mt-4 text-sm break-words text-text-secondary">
          When you resubmit, this application returns to{" "}
          <strong>{resubmission.returns_to_stage.role_label}</strong>.
        </p>
      )}

      {resubmission.can_resubmit && (
        <Link
          href={`/applications/${data.application.id}/edit`}
          className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 sm:w-auto"
        >
          Edit &amp; resubmit
        </Link>
      )}
    </section>
  );
}