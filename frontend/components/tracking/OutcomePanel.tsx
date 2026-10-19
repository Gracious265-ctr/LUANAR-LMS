import Link from "next/link";
import { AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/format";
import type { TrackingResponse } from "@/lib/tracking/types";
import { STATUS_BORDER, STATUS_STYLES, STATUS_TEXT } from "@/lib/status-styles";

/**
 * Attention panel: rejection details with the two choices open to the
 * applicant — correct and resubmit, or accept the rejection as it stands.
 * Rendered only while ``rejection`` is non-null.
 *
 * Accepting is not terminal: it only returns the applicant to their list, and
 * the application stays resubmittable until it is left as-is.
 */
export function OutcomePanel({ data }: { data: TrackingResponse }) {
  const outcome = data.rejection;
  if (!outcome) return null;

  const resubmission = data.resubmission;

  return (
    <section
      aria-label="Rejection details"
      className={cn(
        "rounded-xl border bg-surface-card p-5 shadow-subtle",
        STATUS_BORDER.rejected
      )}
    >
      <div className={cn("flex items-center gap-2", STATUS_TEXT.rejected)}>
        <AlertCircle className="h-5 w-5" aria-hidden="true" />
        <h2 className="text-base font-semibold text-text-primary">
          Rejection details
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
          <dt className="text-xs font-medium text-text-muted">Reason</dt>
          <dd
            className={cn(
              "mt-1 rounded-lg border-l-2 px-3 py-2 break-words whitespace-pre-line",
              STATUS_STYLES.rejected
            )}
          >
            {outcome.reason}
          </dd>
        </div>
      </dl>

      {/* The rejection ends the workflow here — stated once, in the panel
          that owns the outcome, rather than repeated under every stage. */}
      <p className="mt-4 text-sm font-medium text-text-secondary">
        Workflow stopped.
      </p>

      {resubmission.returns_to_stage && (
        <p className="mt-4 text-sm break-words text-text-secondary">
          When you resubmit, this application returns to{" "}
          <strong>{resubmission.returns_to_stage.role_label}</strong>.
        </p>
      )}

      {resubmission.can_resubmit && (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Link
            href={`/leave/${data.application.id}/edit`}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-ring sm:w-auto"
          >
            Edit &amp; resubmit
          </Link>
          <Link
            href="/leave"
            className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-border-default bg-surface-card px-4 py-2 text-sm font-semibold text-text-secondary transition-colors hover:bg-surface-hover focus-ring sm:w-auto"
          >
            Accept rejection
          </Link>
        </div>
      )}
    </section>
  );
}
