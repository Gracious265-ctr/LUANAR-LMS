"use client";

import { Loader2, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { PLAN_ACTION_META } from "@/lib/plans/labels";
import { postPlanDecision } from "@/lib/plans/service";
import type {
  PlanApprovalDetail,
  PlanDecisionAction,
  PlanDetail,
} from "@/lib/plans/types";
import { cn } from "@/lib/utils";

const MAX_COMMENT = 1000;

export interface PlanDecisionDialogProps {
  kind: PlanDecisionAction | null;
  data: PlanApprovalDetail;
  onClose: () => void;
  onSubmitted: (briefing: PlanDetail) => void;
  onReloadRequest: () => void;
}

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
  kind: PlanDecisionAction;
  data: PlanApprovalDetail;
  onClose: () => void;
  onSubmitted: (briefing: PlanDetail) => void;
  onReloadRequest: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const counterId = useId();
  const errorId = useId();

  const meta = PLAN_ACTION_META[kind];
  const requiresComment = kind === "reject";
  const employee = data.employee;
  const dateRange =
    data.blocks.length > 0
      ? `${formatDate(data.blocks[0].start_date)} → ${formatDate(
          data.blocks[data.blocks.length - 1].end_date
        )}`
      : "—";

  useEffect(() => {
    requestAnimationFrame(() => textareaRef.current?.focus());
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
    try {
      const result = await postPlanDecision(data.meta.id, {
        action: kind,
        comment: comment.trim(),
        stage_version: data.decision_version ?? 1,
      });
      if (result.ok) {
        onSubmitted(result.data);
      } else if (result.kind === "conflict") {
        setConflict(true);
        setError(result.message);
      } else {
        setError(result.message);
        if (result.kind === "validation" && result.fields) {
          if (result.fields.comment) setFieldError("comment");
          if (result.fields.stage_version) {
            setConflict(true);
            setError("This plan has already been decided. Refresh to see the latest state.");
          }
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="w-full max-w-md rounded-xl border border-border-default bg-surface-card p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-text-primary">
              {meta.shortLabel} plan
            </h2>
            <p className="mt-0.5 text-sm text-text-secondary">
              {employee.name} · {dateRange}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label
              htmlFor={counterId}
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              Comment {requiresComment && <span className="text-status-rejected">(required)</span>}
            </label>
            <textarea
              ref={textareaRef}
              id={counterId}
              maxLength={MAX_COMMENT}
              value={comment}
              onChange={(e) => {
                setComment(e.target.value);
                if (fieldError) setFieldError("");
              }}
              rows={4}
              className={cn(
                "w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus",
                fieldError === "comment" && "border-status-rejected"
              )}
              placeholder={
                requiresComment
                  ? "Explain why this plan is being rejected."
                  : "Optional note for the applicant."
              }
            />
            <div className="mt-1 text-right text-xs text-text-muted">
              {comment.length}/{MAX_COMMENT}
            </div>
          </div>

          <div aria-live="polite">
            {conflict && (
              <p
                id={errorId}
                className="rounded-lg border border-status-rejected bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected"
              >
                {error}
              </p>
            )}
            {error && !conflict && (
              <p
                id={errorId}
                className="rounded-lg border border-status-rejected bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected"
              >
                {error}
              </p>
            )}
          </div>

          <div className="flex items-center justify-end gap-2">
            {conflict ? (
              <button
                type="button"
                onClick={onReloadRequest}
                className="inline-flex items-center gap-1 rounded-md border border-border-default px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover"
              >
                <RefreshCw className="size-4" />
                Reload
              </button>
            ) : (
              <button
                type="button"
                onClick={onClose}
                disabled={busy}
                className="inline-flex items-center rounded-md border border-border-default px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={busy}
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-4 py-2 text-sm font-medium disabled:opacity-60",
                meta.buttonClass
              )}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {busy ? "Recording…" : meta.shortLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}