"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useId, useRef, useState } from "react";

import { formatDate } from "@/lib/approvals/format";
import { ACTION_META } from "@/lib/approvals/labels";
import { postDecision } from "@/lib/approvals/service";
import type {
  ApprovalAction,
  ApprovalReview,
  DecisionBriefing,
} from "@/lib/approvals/types";
import { cn } from "@/lib/utils";
import { Alert } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

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
  const fieldId = useId();
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
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next && !busy) onClose();
      }}
    >
      <DialogContent
        className="gap-0 max-h-[calc(100vh-4rem)] overflow-y-auto"
        showCloseButton={!busy}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          textareaRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <div>
          <DialogTitle>{meta.label} application</DialogTitle>
          <DialogDescription className="mt-0.5">
            {app.reference} · {data.employee_info.name}
          </DialogDescription>
          <p className="mt-0.5 text-sm text-text-muted">
            {leaveType} · {dateRange}
          </p>
        </div>

        <p className="mt-4 text-sm text-text-secondary">{extraLine}</p>

        <form onSubmit={submit} className="mt-4">
          <div>
            <label
              htmlFor={fieldId}
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              {kind === "approve" ? "Comment (optional)" : "Reason (required)"}
            </label>
            <textarea
              ref={textareaRef}
              id={fieldId}
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
              <Alert
                tone={blocked ? "pending" : "rejected"}
                className="mt-4 flex-col gap-0"
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
              </Alert>
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
      </DialogContent>
    </Dialog>
  );
}