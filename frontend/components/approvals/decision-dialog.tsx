"use client";

import { Loader2, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { formatDate } from "@/lib/approvals/format";
import { ACTION_META } from "@/lib/approvals/labels";
import { postDecision } from "@/lib/approvals/service";
import type {
  ApprovalAction,
  ApprovalReview,
  DecisionBriefing,
} from "@/lib/approvals/types";
import { cn } from "@/lib/utils";

const MAX_COMMENT = 1000;

export interface DecisionDialogProps {
  kind: ApprovalAction | null;
  data: ApprovalReview;
  onClose: () => void;
  onSubmitted: (briefing: DecisionBriefing) => void;
  onReloadRequest: () => void;
}

export function DecisionDialog(props: DecisionDialogProps) {
  if (props.kind === null) return null;
  const { kind } = props;
  return (
    <DecisionDialogInner
      key={`${kind}-${props.data.application.id}`}
      kind={kind}
      data={props.data}
      onClose={props.onClose}
      onSubmitted={props.onSubmitted}
      onReloadRequest={props.onReloadRequest}
    />
  );
}

function DecisionDialogInner({
  kind,
  data,
  onClose,
  onSubmitted,
  onReloadRequest,
}: {
  kind: ApprovalAction;
  data: ApprovalReview;
  onClose: () => void;
  onSubmitted: (briefing: DecisionBriefing) => void;
  onReloadRequest: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const counterId = useId();
  const errorId = useId();

  const requiresComment = kind === "reject" || kind === "return_for_correction";
  const pendingStage = data.workflow.stages.find((stage) => stage.status === "pending");
  const stageVersion = pendingStage?.decision_version ?? 1;
  const app = data.application;
  const leaveType = data.rules.leave_type.name || "Leave";
  const dateRange =
    app.start_date && app.end_date
      ? `${formatDate(app.start_date)} → ${formatDate(app.end_date)}`
      : "—";

  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => textareaRef.current?.focus());
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

  const validatedConfirm = requiresComment ? comment.trim().length > 0 : true;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!validatedConfirm) {
      setError("Please enter a comment.");
      setFieldError("comment");
      return;
    }
    setBusy(true);
    setError("");
    setFieldError("");
    setConflict(false);
    setBlocked(false);
    try {
      const result = await postDecision(app.id, {
        action: kind,
        comment: comment.trim(),
        stage_version: stageVersion,
      });
      if (result.ok) {
        onSubmitted(result.data);
      } else if (result.kind === "conflict") {
        setConflict(true);
        setError(result.message);
      } else if (result.kind === "blocked") {
        // Permanent: there is no approver left for this application, so the
        // dialog offers no Refresh and the approver simply cannot decide.
        setBlocked(true);
        setError(result.message);
      } else if (result.kind === "forbidden") {
        setError(result.message);
        onReloadRequest();
        onClose();
      } else if (result.kind === "validation") {
        setFieldError(result.fields?.comment ?? "comment");
        setError(result.fields?.comment ?? result.message);
      } else if (result.kind === "not_found") {
        setError(result.message);
      } else {
        setError(result.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const meta = ACTION_META[kind];
  const ConfirmIcon = meta.icon;

  const extraLine =
    kind === "approve"
      ? data.workflow.current_stage?.is_final
        ? "This is the final approval stage. Approving will finalise this leave application."
        : data.workflow.current_stage?.next_role_label
          ? `Next stage: ${data.workflow.current_stage.next_role_label}.`
          : "Approve this application."
      : kind === "reject"
        ? "The workflow will stop. The employee can edit and resubmit."
        : "The employee will be asked to correct and resubmit this application.";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 pt-[12vh]"
    >
      <div
        data-testid="decision-dialog-overlay"
        onClick={() => !busy && onClose()}
        className="fixed inset-0 bg-black/40"
        aria-hidden="true"
      />
      <div className="relative w-full max-w-lg rounded-xl border border-border-default bg-surface-card p-6 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 id={titleId} className="text-lg font-semibold text-text-primary">
              {meta.label} application
            </h3>
            <p className="mt-0.5 text-sm text-text-secondary">
              {app.reference} · {data.employee_info.name}
            </p>
            <p className="mt-0.5 text-sm text-text-muted">
              {leaveType} · {dateRange}
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

        <p className="mt-4 text-sm text-text-secondary">{extraLine}</p>

        <form onSubmit={submit} className="mt-4">
          <div>
            <label
              htmlFor={`${titleId}-comment`}
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              {kind === "approve" ? "Comment (optional)" : "Reason (required)"}
            </label>
            <textarea
              ref={textareaRef}
              id={`${titleId}-comment`}
              name="comment"
              rows={4}
              maxLength={MAX_COMMENT}
              aria-describedby={`${counterId} ${fieldError ? errorId : ""}`}
              aria-invalid={!!fieldError}
              value={comment}
              onChange={(event) => {
                setComment(event.target.value);
                if (fieldError) setFieldError("");
              }}
              className={cn(
                "w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus",
                fieldError &&
                  "border-status-rejected focus:border-status-rejected focus:ring-status-rejected/30"
              )}
              placeholder={
                kind === "approve"
                  ? "Optional comment for the employee."
                  : "Explain what needs to happen in this application."
              }
            />
            <div className="mt-1 flex items-center justify-between">
              <span id={errorId} aria-live="polite" className="text-xs text-status-rejected">
                {fieldError}
              </span>
              <span id={counterId} className="text-xs text-text-muted">
                {comment.length} / {MAX_COMMENT}
              </span>
            </div>
          </div>

          <div aria-live="polite">
            {error && !fieldError && !conflict && (
              <div
                role="alert"
                className={cn(
                  "mt-4 rounded-lg p-3 text-sm",
                  blocked
                    ? "bg-status-pending-subtle text-status-pending"
                    : "bg-status-rejected-subtle text-status-rejected"
                )}
              >
                {error}
                {blocked && (
                  <p className="mt-1 text-xs">
                    Reloading will not help. This application&apos;s final stage
                    resolves to the applicant, so Human Resources must change the
                    applicant&apos;s approver role or the workflow before it can be
                    decided.
                  </p>
                )}
              </div>
            )}
          </div>

          {conflict && (
            <div className="mt-4 rounded-lg bg-status-pending-subtle p-3 text-sm text-status-pending">
              This application has changed since you opened it.{" "}
              <button
                type="button"
                onClick={onReloadRequest}
                className="inline-flex items-center gap-1 font-medium text-brand-primary hover:underline"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Reload
              </button>
            </div>
          )}

          <div className="mt-5 flex items-center gap-3">
            <button
              type="submit"
              disabled={busy || blocked || !validatedConfirm}
              className={cn(
                "inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2 font-medium focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
                meta.buttonClass
              )}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <ConfirmIcon className="h-4 w-4" aria-hidden="true" />
              )}
              {busy ? "Submitting…" : meta.label}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onClose}
              className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}