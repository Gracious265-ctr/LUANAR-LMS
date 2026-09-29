"use client";

import { Check, Loader2, RefreshCw, X } from "lucide-react";
import { useId, useRef, useState } from "react";

import { postCancellationDecision } from "@/lib/cancellations/service";
import type { CancellationDetail } from "@/lib/cancellations/types";
import { cn } from "@/lib/utils";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

const MAX_COMMENT = 1000;

export interface CancellationDecisionDialogProps {
  kind: "approve" | "reject" | null;
  data: CancellationDetail;
  onClose: () => void;
  onSubmitted: (data: CancellationDetail) => void;
  onConflict: () => void;
}

export function CancellationDecisionDialog(props: CancellationDecisionDialogProps) {
  if (props.kind === null) return null;
  const { kind, data } = props;
  return (
    <CancellationDecisionDialogInner
      key={`${kind}-${data.request.id}`}
      kind={kind}
      data={data}
      onClose={props.onClose}
      onSubmitted={props.onSubmitted}
      onConflict={props.onConflict}
    />
  );
}

function CancellationDecisionDialogInner({
  kind,
  data,
  onClose,
  onSubmitted,
  onConflict,
}: {
  kind: "approve" | "reject";
  data: CancellationDetail;
  onClose: () => void;
  onSubmitted: (data: CancellationDetail) => void;
  onConflict: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fieldId = useId();
  const counterId = useId();
  const errorId = useId();

  const requiresComment = kind === "reject";

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
    try {
      const result = await postCancellationDecision(data.request.id, {
        decision: kind,
        comment: comment.trim(),
        stage_version: data.stage_version,
      });
      if (result.ok) {
        onSubmitted(result.data);
      } else if (result.kind === "conflict") {
        onConflict();
        onClose();
      } else if (result.kind === "forbidden") {
        setError(result.message);
      } else if (result.kind === "validation") {
        setFieldError(result.fields?.comment ?? "comment");
        setError(result.fields?.comment ?? result.message);
      } else {
        setError(result.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const isApprove = kind === "approve";
  const label = isApprove ? "Approve cancellation" : "Reject cancellation";

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
          <DialogTitle>{label}</DialogTitle>
          <DialogDescription className="mt-0.5">
            {data.application.reference} · {data.application.leave_type.name || "Leave"}
          </DialogDescription>
        </div>

        <p className="mt-4 text-sm text-text-secondary">
          {isApprove
            ? data.leave_started
              ? "This leave has already started; it can only be rejected."
              : "Approving will cancel this leave and restore the recorded annual-balance days."
            : "Rejecting keeps the leave approved. The employee will be notified."}
        </p>

        <p className="mt-4 text-sm font-medium text-text-primary">Employee&apos;s reason</p>
        <p className="mt-1 whitespace-pre-wrap rounded-lg bg-surface-muted p-3 text-sm text-text-secondary">
          {data.request.reason}
        </p>

        <form onSubmit={submit} className="mt-4">
          <div>
            <label
              htmlFor={fieldId}
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              {isApprove ? "Comment (optional)" : "Reason (required)"}
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
                isApprove
                  ? "Optional comment for the employee."
                  : "Explain why the cancellation is not approved."
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
            {error && !fieldError && (
              <Alert tone="rejected" className="mt-4">
                {error}
              </Alert>
            )}
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button
              type="submit"
              variant="secondary"
              disabled={busy || !validatedConfirm}
              className={cn(
                isApprove
                  ? "border border-transparent bg-[#009119] text-white hover:bg-[#008017]"
                  : "border border-status-rejected bg-status-rejected-subtle text-status-rejected hover:bg-surface-hover"
              )}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : isApprove ? (
                <Check className="h-4 w-4" aria-hidden="true" />
              ) : (
                <X className="h-4 w-4" aria-hidden="true" />
              )}
              {busy ? "Submitting…" : isApprove ? "Approve" : "Reject"}
            </Button>
            <Button type="button" disabled={busy} onClick={onClose} variant="secondary">
              Cancel
            </Button>
            {data.leave_started && (
              <span className="inline-flex items-center gap-1 text-xs text-status-pending">
                <RefreshCw className="h-3 w-3" aria-hidden="true" />
                Leave already started
              </span>
            )}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}