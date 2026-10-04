"use client";

import { CalendarX2, CheckCircle2, ChevronLeft, Loader2 } from "lucide-react";
import { useId, useRef, useState } from "react";

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
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";

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
const fieldId = useId();
  const counterId = useId();
  const errorId = useId();

  const trimmed = reason.trim();
  const reasonValid = trimmed.length >= MIN_REASON && trimmed.length <= MAX_REASON;

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
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next && !busy) onClose();
      }}
    >
      <DialogContent
        scrollClassName="gap-0"
        scrollable
        showCloseButton={!busy}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          reasonRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <div>
          <DialogTitle>
            {action === "withdraw" ? "Withdraw application" : "Request cancellation"}
          </DialogTitle>
          <DialogDescription className="mt-0.5">
            {application.reference_number} · {application.leave_type?.name || "Leave"} ·{" "}
            {dateRange} · {application.working_days} working day
            {application.working_days === 1 ? "" : "s"}
          </DialogDescription>
        </div>

        {error && (
          <Alert
            tone={conflict ? "pending" : "rejected"}
            className="mt-4 flex-col gap-0"
          >
            {error}
            {conflict && pendingEligibility && (
              <Button
                type="button"
                disabled={busy}
                onClick={() => onActionChanged(pendingEligibility)}
                variant="link"
                size="sm"
                className="mt-2 h-auto block"
              >
                Refresh and review the latest state
              </Button>
            )}
          </Alert>
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
                htmlFor={fieldId}
                className="mb-1 block text-sm font-medium text-text-primary"
              >
                Reason (required)
              </label>
              <textarea
                ref={reasonRef}
                id={fieldId}
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
              <Button type="submit" variant="primary">
                Continue
              </Button>
              <Button type="button" onClick={onClose} variant="secondary">
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <form onSubmit={submit} className="mt-4">
            <Card className="shadow-none">
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
            </Card>

            <div className="mt-5 flex items-center gap-3">
              <Button
                type="button"
                disabled={busy}
                onClick={() => setStep(1)}
                variant="secondary"
                size="sm"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                Back
              </Button>
              <Button type="submit" disabled={busy} variant="primary" className="flex-1">
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                )}
                {busy ? "Submitting…" : confirmLabel(action)}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}