"use client";

import { Loader2 } from "lucide-react";
import { useId, useRef, useState } from "react";

import { formatPeriod } from "@/lib/plans/format";
import { ACTION_META, restrictionTitle } from "@/lib/plans/labels";
import { postPlanDecision } from "@/lib/plans/service";
import type { PlanAction, PlanApprovalDetail } from "@/lib/plans/types";
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

export interface PlanDecisionDialogProps {
  kind: PlanAction | null;
  data: PlanApprovalDetail;
  onClose: () => void;
  onSubmitted: () => void;
  onReloadRequest: () => void;
}

/**
 * Recording an approve or reject on a plan.
 *
 * The comment is required to reject, because a rejection stops the chain for
 * good — a plan is not resubmittable, so the owner cannot correct it and come
 * back. `stage_version` is read once when the dialog opens rather than per
 * render, so the version the approver confirmed is the one that is checked.
 */
export function PlanDecisionDialog(props: PlanDecisionDialogProps) {
  if (props.kind === null) return null;
  const { kind } = props;
  return (
    <PlanDecisionDialogInner
      key={`${kind}-${props.data.meta.id}`}
      kind={kind}
      data={props.data}
      onClose={props.onClose}
      onSubmitted={props.onSubmitted}
      onReloadRequest={props.onReloadRequest}
    />
  );
}

function PlanDecisionDialogInner({
  kind,
  data,
  onClose,
  onSubmitted,
  onReloadRequest,
}: {
  kind: PlanAction;
  data: PlanApprovalDetail;
  onClose: () => void;
  onSubmitted: () => void;
  onReloadRequest: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fieldId = useId();
  const counterId = useId();
  const errorId = useId();

  const requiresComment = kind === "reject";
  const stageVersion = data.decision_version ?? 1;
  const validatedConfirm = requiresComment ? comment.trim().length > 0 : true;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!validatedConfirm) {
      setError("Please enter a reason.");
      setFieldError("comment");
      return;
    }
    setBusy(true);
    setError("");
    setFieldError("");
    setConflict(false);
    try {
      const result = await postPlanDecision(data.meta.id, {
        action: kind,
        comment: comment.trim(),
        stage_version: stageVersion,
      });
      if (result.ok) {
        onSubmitted();
      } else if (result.kind === "conflict") {
        // Somebody in the candidate set acted first. The plan is decided, so
        // the only useful next step is re-reading it.
        setConflict(true);
        setError(result.message);
      } else if (result.kind === "forbidden") {
        setError(result.message);
        onClose();
        onReloadRequest();
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

  const meta = ACTION_META[kind];
  const ConfirmIcon = meta.icon;

  const outcomeLine =
    kind === "approve"
      ? data.stages.find((stage) => stage.status === "pending")?.is_final
        ? "This is the final stage. Approving reserves the leave for each block."
        : "Approving passes this plan to the next stage."
      : "Rejecting stops here. A plan cannot be resubmitted, so the leave will need a new plan.";

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
          textareaRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <div>
          <DialogTitle>{restrictionTitle(kind)}</DialogTitle>
          <DialogDescription className="mt-0.5">
            {formatPeriod(data.meta.period_start, data.meta.period_end)} ·{" "}
            {data.employee.name}
          </DialogDescription>
          <p className="mt-0.5 text-sm text-text-muted">
            {data.blocks.length} {data.blocks.length === 1 ? "block" : "blocks"} ·{" "}
            {data.blocks.reduce((total, block) => total + (block.working_days ?? 0), 0)}{" "}
            working days
          </p>
        </div>

        <p className="mt-4 text-sm text-text-secondary">{outcomeLine}</p>

        <form onSubmit={submit} className="mt-4">
          <div>
            <label
              htmlFor={fieldId}
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              {requiresComment ? "Reason (required)" : "Comment (optional)"}
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
                requiresComment
                  ? "Explain why this plan cannot be approved."
                  : "Optional comment for the employee."
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
              <Alert tone="rejected" className="mt-4 flex-col gap-0">
                {error}
              </Alert>
            )}
          </div>

          {conflict && (
            <div className="mt-4 rounded-lg bg-status-pending-subtle p-3 text-sm text-status-pending">
              This plan has changed since you opened it.{" "}
              <Button
                type="button"
                onClick={onReloadRequest}
                variant="link"
                size="sm"
                className="h-auto"
              >
                Reload
              </Button>
            </div>
          )}

          <div className="mt-5 flex items-center gap-3">
            <Button
              type="submit"
              variant="secondary"
              disabled={busy || !validatedConfirm}
              className={cn("border-transparent", meta.buttonClass)}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <ConfirmIcon className="h-4 w-4" aria-hidden="true" />
              )}
              {busy ? "Saving…" : meta.shortLabel}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={busy}
            >
              Cancel
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
