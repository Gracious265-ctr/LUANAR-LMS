"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Loader2, RefreshCw, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";

import { ApiError } from "@/lib/approvals/service";
import { BLOCKED_REASON_TEXT } from "@/lib/cancellation/labels";
import { submitCancellation } from "@/lib/cancellation/service";
import type {
  CancellationAction,
  CancellationEligibility,
  SubmitCancellationInput,
} from "@/lib/cancellation/types";
import { formatDate } from "@/lib/tracking/format";
import type { ApplicationSummary } from "@/lib/tracking/types";

import { Dialog, DialogHeader } from "../ui/dialog";
import { Textarea } from "../ui/textarea";

const MIN_REASON = 10;
const MAX_REASON = 1000;

interface SubmitError {
  kind: "field" | "inline";
  message: string;
  reasonError?: string;
}

/** Human note for the confirm step's recap. */
function consequenceNote(action: CancellationAction): string {
  return action === "withdraw"
    ? "This application will be withdrawn immediately. No leave days have been deducted, so nothing will be restored."
    : "If approved, the leave will be cancelled. Your leave stays active until a decision is made.";
}

/**
 * Two-step cancellation dialog ("Details" then "Confirm"). The reason limits
 * mirror the backend for UX only — the server stays authoritative. After a
 * successful submit the parent is told to refetch (the backend owns final
 * state; nothing is optimistically updated).
 */
export function CancelApplicationDialog({
  open,
  onClose,
  application,
  eligibility,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  application: Pick<
    ApplicationSummary,
    | "id"
    | "reference_number"
    | "leave_type"
    | "start_date"
    | "end_date"
    | "working_days"
  >;
  eligibility: Pick<
    CancellationEligibility,
    "cancellation_action" | "estimated_restoration_days"
  >;
  onSuccess: () => void;
}) {
  const titleId = useId();
  const [step, setStep] = useState<1 | 2>(1);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<SubmitError | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const pendingActionChange = useRef(false);

  const action = eligibility.cancellation_action;
  const trimmed = reason.trim();
  const tooShort = trimmed.length < MIN_REASON;
  const tooLong = trimmed.length > MAX_REASON;
  const reasonInvalid = (step === 1 && tooShort) || tooLong;
  const normalized = trimmed.slice(0, MAX_REASON);

  // After an action_changed conflict the parent refetches the live payload;
  // when the fresh eligibility arrives its action differs, so drop the stale
  // dialog back to step 1 (and clear the "refreshing" banner).
  useEffect(() => {
    if (!pendingActionChange.current) return;
    pendingActionChange.current = false;
    setStep(1);
    setError(null);
    setRefreshing(false);
    setReason("");
  }, [action]);

  function reset() {
    setStep(1);
    setError(null);
    setRefreshing(false);
    setReason("");
    setSubmitting(false);
  }

  function close() {
    if (submitting) return;
    reset();
    onClose();
  }

  function goToConfirm() {
    setError(null);
    if (tooShort || tooLong) {
      setError({
        kind: "field",
        message: "Please check the reason below.",
        reasonError:
          trimmed.length === 0
            ? "A reason is required."
            : tooShort
              ? `The reason must be at least ${MIN_REASON} characters.`
              : `The reason must be at most ${MAX_REASON} characters.`,
      });
      return;
    }
    setStep(2);
  }

  async function handleSubmit() {
    if (!action || submitting) return;
    setSubmitting(true);
    setError(null);
    const input: SubmitCancellationInput = {
      reason: normalized,
      confirm: true,
      expected_action: action,
    };
    try {
      await submitCancellation(application.id, input);
      reset();
      onSuccess();
      onClose();
    } catch (err) {
      if (handleSubmitError(err)) return;
    } finally {
      setSubmitting(false);
    }
  }

  /** Returns true when a stale-state conflict was surfaced (dialog stays open). */
  function handleSubmitError(err: unknown): boolean {
    if (!(err instanceof ApiError)) {
      setError({
        kind: "inline",
        message: "You are offline or the service is unavailable. Please try again.",
      });
      return false;
    }
    const code = extractCode(err.data);
    switch (code) {
      case "action_changed":
        // Drift between page load and submit: surface a message and have the
        // parent refetch the live tracking payload so the stale dialog state
        // is replaced by fresh eligibility data on the next open.
        setError({
          kind: "inline",
          message: "The application changed since you opened this dialog.",
        });
        setRefreshing(true);
        pendingActionChange.current = true;
        onSuccess();
        return true;
      case "reason_too_short":
      case "reason_too_long":
        setError({
          kind: "field",
          message:
            "The reason must be between 10 and 1000 characters after trimming.",
          reasonError:
            code === "reason_too_short"
              ? `The reason must be at least ${MIN_REASON} characters.`
              : `The reason must be at most ${MAX_REASON} characters.`,
        });
        if (step !== 1) setStep(1);
        return true;
      case "confirmation_required":
        setError({
          kind: "inline",
          message: "Confirmation is required before submitting.",
        });
        return true;
      default:
        if (code && code in BLOCKED_REASON_TEXT) {
          setError({
            kind: "inline",
            message: BLOCKED_REASON_TEXT[code as keyof typeof BLOCKED_REASON_TEXT],
          });
        } else if (isConflictStatus(err.status) && code === "request_not_pending") {
          setError({ kind: "inline", message: "This request is no longer pending." });
        } else {
          setError({
            kind: "inline",
            message: extractDetail(err.data),
          });
        }
        return true;
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      labelledBy={titleId}
      blockDismiss={submitting}
    >
      <DialogHeader
        titleId={titleId}
        title={
          action === "withdraw" ? "Withdraw application" : "Request cancellation"
        }
        subtitle={application.reference_number}
        onClose={close}
        blockDismiss={submitting}
      />

      {step === 1 ? (
        <div className="space-y-5 px-6 py-5">
          <dl className="space-y-1 rounded-lg bg-surface-subtle px-4 py-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">Leave type</dt>
              <dd className="font-medium text-text-primary">
                {application.leave_type?.name || "Leave"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">Period</dt>
              <dd className="font-medium text-text-primary">
                {formatDate(application.start_date)} –{" "}
                {formatDate(application.end_date)}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">Working days</dt>
              <dd className="font-medium text-text-primary">
                {application.working_days}
              </dd>
            </div>
          </dl>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="cancel-reason"
                className="text-sm font-medium text-text-primary"
              >
                Reason{action === "withdraw" ? " for withdrawal" : ""}
              </label>
              <span
                className={cn(
                  "text-xs tabular-nums",
                  tooLong
                    ? "font-semibold text-status-rejected"
                    : "text-text-muted"
                )}
              >
                {trimmed.length}/{MAX_REASON}
              </span>
            </div>
            <Textarea
              id="cancel-reason"
              name="reason"
              value={reason}
              onChange={(event) => {
                setReason(event.target.value);
                if (error?.kind === "field") setError(null);
              }}
              placeholder="Explain why you are canceling this leave…"
              aria-invalid={Boolean(error?.kind === "field" && error.reasonError)}
              aria-describedby={
                error?.kind === "field" && error.reasonError
                  ? "cancel-reason-error"
                  : undefined
              }
              disabled={submitting}
            />
            {error?.kind === "field" && error.reasonError && (
              <p
                id="cancel-reason-error"
                role="alert"
                className="flex items-start gap-1.5 text-sm text-status-rejected"
              >
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                {error.reasonError}
              </p>
            )}
          </div>

          <div className="space-y-2">
            {action === "request" && (
              <p className="text-sm text-text-secondary">
                Your Supervisor/HOD must approve this. Your leave stays active
                until then.
              </p>
            )}
            {action === "withdraw" && (
              <p className="text-sm text-text-secondary">
                This application will be withdrawn immediately.
              </p>
            )}
            {action === "request" &&
              Number(eligibility.estimated_restoration_days) > 0 && (
                <p className="text-sm text-text-secondary">
                  About{" "}
                  <span className="font-medium text-text-primary">
                    {eligibility.estimated_restoration_days}
                  </span>{" "}
                  annual leave{" "}
                  {Number(eligibility.estimated_restoration_days) === 1
                    ? "day"
                    : "days"}{" "}
                  will be restored to your FY balance if approved.
                </p>
              )}
          </div>

          {error && !error.reasonError && (
            <p
              role="alert"
              className="flex items-start gap-1.5 text-sm text-status-rejected"
            >
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {error.message}
            </p>
          )}

          <div className="flex justify-end gap-3 border-t border-border-default pt-4">
            <button
              type="button"
              onClick={close}
              disabled={submitting}
              className="inline-flex min-h-11 items-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={goToConfirm}
              disabled={reasonInvalid || submitting}
              className="inline-flex min-h-11 items-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Continue
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-5 px-6 py-5">
          <div className="space-y-2 rounded-lg bg-surface-subtle px-4 py-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">Reason</dt>
              <dd className="font-medium break-words whitespace-pre-line text-text-primary">
                {normalized}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">Consequence</dt>
              <dd className="text-right font-medium text-text-primary">
                {consequenceNote(action ?? "request")}
              </dd>
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="flex items-start gap-1.5 text-sm text-status-rejected"
            >
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {error.message}
            </p>
          )}

          {refreshing && (
            <p
              role="status"
              className="flex items-center gap-1.5 rounded-lg bg-status-correction-subtle px-3 py-2 text-sm text-status-correction"
            >
              <RefreshCw className="h-4 w-4 shrink-0" aria-hidden="true" />
              Refreshing to the latest application state…
            </p>
          )}

          <div className="flex justify-between gap-3 border-t border-border-default pt-4">
            <button
              type="button"
              onClick={() => setStep(1)}
              disabled={submitting}
              className="inline-flex min-h-11 items-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className={cn(
                "inline-flex min-h-11 items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
                action === "withdraw"
                  ? "bg-status-rejected hover:bg-status-rejected/90"
                  : "bg-brand-primary hover:bg-brand-primary-hover"
              )}
            >
              {submitting && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {action === "withdraw"
                ? "Yes, withdraw application"
                : "Submit cancellation request"}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function isConflictStatus(status: number): boolean {
  return status === 409 || status === 422;
}

function extractCode(data: unknown): string | null {
  if (data && typeof data === "object" && "code" in data) {
    return String((data as { code: unknown }).code);
  }
  return null;
}

function extractDetail(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    return String((data as { detail: unknown }).detail);
  }
  return "The cancellation could not be submitted. Please try again.";
}