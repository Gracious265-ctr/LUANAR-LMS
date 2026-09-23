import { AlertCircle, CornerUpLeft } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import type { ResubmissionFeedback } from "@/lib/applications/resubmission-types";

/**
 * The rejection / correction banner surfaced both on the tracker and at the top
 * of the resubmission edit page. Mirrors the outcome panel accent styling.
 */
export function ApproverFeedbackCard({
  feedback,
  className,
}: {
  feedback: ResubmissionFeedback | null;
  className?: string;
}) {
  if (!feedback) return null;

  const isRejected = feedback.action === "reject";
  const Icon = isRejected ? AlertCircle : CornerUpLeft;

  return (
    <section
      aria-label={isRejected ? "Rejection feedback" : "Correction feedback"}
      className={cn(
        "rounded-xl border bg-surface-card p-5 shadow-subtle",
        isRejected
          ? "border-status-rejected/30"
          : "border-status-correction/30",
        className
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
            isRejected
              ? "bg-status-rejected-subtle text-status-rejected"
              : "bg-status-correction-subtle text-status-correction"
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <h2 className="text-base font-semibold text-text-primary">
          {isRejected ? "Application rejected" : "Correction requested"}
        </h2>
      </div>

      <p className="mt-3 text-sm break-words text-text-secondary">
        <strong className="font-medium text-text-primary">
          {feedback.approver_name}
        </strong>{" "}
        · {feedback.role_label}
        {feedback.decided_at && (
          <>
            {" · "}
            <time dateTime={feedback.decided_at}>
              {formatDateTime(feedback.decided_at)}
            </time>
          </>
        )}
      </p>

      {feedback.comment && (
        <p className="mt-2 rounded-lg border-l-2 bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
          {feedback.comment}
        </p>
      )}
    </section>
  );
}