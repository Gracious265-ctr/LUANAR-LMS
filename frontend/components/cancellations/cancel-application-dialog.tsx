"use client";

import { CalendarX2, CheckCircle2, ChevronLeft, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { confirmLabel, consequenceLine } from "@/lib/cancellations/labels";
import { submitCancellation } from "@/lib/cancellations/service";
import type {
  CancellationAction,
  CancellationEligibility,
  SubmitCancellationResult,
} from "@/lib/cancellations/types";
import { formatDate } from "@/lib/tracking/format";
import type { ApplicationSummary } from "@/lib/tracking/types";
import { cn } from "@/lib/utils";

const MAX_REASON = 1000;
const MIN_REASON = 10;

export interface CancelApplicationDialogProps {
  action: CancellationAction;
  eligibility: CancellationEligibility;
  application: ApplicationSummary;
  onClose: () => void;
  onSubmitted: (result: SubmitCancellationResult & { ok: true }) => void;
  onActionChanged: (eligibility: CancellationEligibility) => void;
}

export function CancelApplicationDialog(props: CancelApplicationDialogProps) {
  const { action, eligibility, application } = props;
  return (
    <CancelApplicationDialogInner
      key={`${action}-${eligibility.application_id}`}
      action={action}
      eligibility={eligibility}
      application={application}
      onClose={props.onClose}
      onSubmitted={props.onSubmitted}
      onActionChanged={props.onActionChanged}
    />
  );
}

function CancelApplicationDialogInner({
  action,
  eligibility,
  application,
  onClose,
  onSubmitted,
  onActionChanged,
}: CancelApplicationDialogProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [showReasonError, setShowReasonError] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
const reasonRef = useRef<HTMLTextAreaElement>(null);
const [pendingEligibility, setPendingEligibility] =
  useState<CancellationEligibility | null>(null);
const titleId = useId();
  const counterId = useId();
  const errorId = useId();

  const trimmed = reason.trim();
  const reasonValid = trimmed.length >= MIN_REASON && trimmed.length <= MAX_REASON;

  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => reasonRef.current?.focus());
    return () => {
      previousFocus.current?.focus?.();
    };
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    },
    [busy, onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  function nextStep() {
    if (!reasonValid) {
      setShowReasonError(true);
      return;
    }
    setError("");
    setShowReasonError(false);
    setStep(2);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setConflict(false);
    try {
      const result = await submitCancellation(eligibility.application_id, {
        reason: trimmed,
        confirm: true,
        expected_action: action,
      });
      if (result.ok) {
        onSubmitted(result);
      } else if (result.code === "action_changed" && result.eligibility) {
        setConflict(true);
        setError(result.message);
        setPendingEligibility(result.eligibility);
      } else {
        setError(result.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const dateRange = application.start_date
    ? `${formatDate(application.start_date)} → ${formatDate(application.end_date)}`
    : "—";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 pt-[10vh]"
    >
      <div
        data-testid="cancel-dialog-overlay"
        onClick={() => !busy && onClose()}
        className="fixed inset-0 bg-black/40"
        aria-hidden="true"
      />
      <div className="relative w-full max-w-lg rounded-xl border border-border-default bg-surface-card p-6 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 id={titleId} className="text-lg font-semibold text-text-primary">
              {action === "withdraw" ? "Withdraw application" : "Request cancellation"}
            </h3>
            <p className="mt-0.5 text-sm text-text-secondary">
              {application.reference_number} · {application.leave_type?.name || "Leave"} ·{" "}
              {dateRange} · {application.working_days} working day
              {application.working_days === 1 ? "" : "s"}
            </p>
          </div>
          <button
            type="button"
            aria-label="Close dialog"
            disabled={busy}
            onClick={onClose}
            className="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className={cn(
              "mt-4 rounded-lg p-3 text-sm",
              conflict
                ? "bg-status-pending-subtle text-status-pending"
                : "bg-status-rejected-subtle text-status-rejected"
            )}
          >
            {error}
            {conflict && pendingEligibility && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onActionChanged(pendingEligibility)}
                className="mt-2 block font-medium text-brand-primary hover:underline"
              >
                Refresh and review the latest state
              </button>
            )}
          </div>
        )}

        {step === 1 ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              nextStep();
            }}
            className="mt-4"
          >
            <div>
              <label
                htmlFor={`${titleId}-reason`}
                className="mb-1 block text-sm font-medium text-text-primary"
              >
                Reason (required)
              </label>
              <textarea
                ref={reasonRef}
                id={`${titleId}-reason`}
                name="reason"
                rows={4}
                maxLength={MAX_REASON}
                value={reason}
                onChange={(event) => {
                  setReason(event.target.value);
                  if (showReasonError) setShowReasonError(false);
                }}
                aria-describedby={`${counterId} ${errorId}`}
                aria-invalid={showReasonError}
                className={cn(
                  "w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus",
                  showReasonError &&
                    "border-status-rejected focus:border-status-rejected focus:ring-status-rejected/30"
                )}
                placeholder="Explain why you need to cancel this leave."
              />
              <div className="mt-1 flex items-center justify-between">
                <span id={errorId} aria-live="polite" className="text-xs text-status-rejected">
                  {showReasonError
                    ? trimmed.length < MIN_REASON
                      ? `The reason must be at least ${MIN_REASON} characters.`
                      : ""
                    : ""}
                </span>
                <span id={counterId} className="text-xs text-text-muted">
                  {reason.length} / {MAX_REASON}
                </span>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-3 rounded-lg bg-surface-muted p-3 text-sm text-text-secondary">
              <CalendarX2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p>
                {consequenceLine(
                  action,
                  eligibility.estimated_restoration_days,
                  eligibility.restoration_financial_year
                )}
              </p>
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 font-medium text-white hover:bg-brand-primary-hover focus:outline-none focus:ring-2 focus:ring-brand-primary/40"
              >
                Continue
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={submit} className="mt-4">
            <div className="rounded-xl border border-border-default bg-surface-card p-4">
              <p className="text-sm font-medium text-text-primary">Reason</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-text-secondary">{trimmed}</p>
              <p className="mt-3 text-sm font-medium text-text-primary">What happens next</p>
              <p className="mt-1 text-sm text-text-secondary">
                {consequenceLine(
                  action,
                  eligibility.estimated_restoration_days,
                  eligibility.restoration_financial_year
                )}
              </p>
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-1 rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                Back
              </button>
              <button
                type="submit"
                disabled={busy}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 font-medium text-white hover:bg-brand-primary-hover focus:outline-none focus:ring-2 focus:ring-brand-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                )}
                {busy ? "Submitting…" : confirmLabel(action)}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}