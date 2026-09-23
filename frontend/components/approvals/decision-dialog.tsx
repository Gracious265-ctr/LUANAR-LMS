"use client";

import { useState } from "react";

import { Check, Loader2, RotateCcw, TriangleAlert, X } from "lucide-react";

import { cn } from "@/lib/utils";

import type { ApprovalDetail, DecisionAction } from "@/lib/approvals/types";

import { Dialog, DialogHeader } from "../ui/dialog";
import { Textarea } from "../ui/textarea";

export type DecisionError =
  | { kind: "conflict"; message: string }
  | { kind: "forbidden"; message: string }
  | { kind: "field"; message: string; commentError?: string }
  | { kind: "other"; message: string };

export const DECISION_CONFIG: Record<
  DecisionAction,
  {
    heading: string;
    confirmLabel: string;
    commentLabel: string;
    commentRequired: boolean;
    hint: string;
    confirmClass: string;
  }
> = {
  approve: {
    heading: "Approve application",
    confirmLabel: "Confirm approval",
    commentLabel: "Comment (optional)",
    commentRequired: false,
    hint: "Confirming will approve this application and move it to the next approval stage.",
    confirmClass: "bg-status-approved text-white hover:bg-status-approved/90",
  },
  reject: {
    heading: "Reject application",
    confirmLabel: "Reject application",
    commentLabel: "Reason (required)",
    commentRequired: true,
    hint: "Rejecting ends the approval process. The employee will be notified with your reason.",
    confirmClass: "bg-status-rejected text-white hover:bg-status-rejected/90",
  },
  return_for_correction: {
    heading: "Return for correction",
    confirmLabel: "Return for correction",
    commentLabel: "Comment (required)",
    commentRequired: true,
    hint: "The employee will be asked to correct and resubmit the application.",
    confirmClass:
      "bg-status-correction text-white hover:bg-status-correction/90",
  },
};

export function DecisionDialog({
  open,
  action,
  detail,
  pending,
  error,
  onClose,
  onSubmit,
  onReload,
}: {
  open: boolean;
  action: DecisionAction;
  detail: ApprovalDetail;
  pending: boolean;
  error: DecisionError | null;
  onClose: () => void;
  onSubmit: (comment: string) => void;
  onReload: () => void;
}) {
  const [comment, setComment] = useState("");
  const config = DECISION_CONFIG[action];
  const titleId = "decision-dialog-title";
  const conflict = error?.kind === "conflict";
  const forbidden = error?.kind === "forbidden";
  const commentError = error?.kind === "field" ? error.commentError : undefined;
  const showForm = !conflict && !forbidden;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      labelledBy={titleId}
      blockDismiss={pending}
      ariaLabel={config.heading}
    >
      <DialogHeader
        titleId={titleId}
        title={config.heading}
        subtitle={`${detail.reference} · ${detail.employee.full_name}`}
        onClose={onClose}
        blockDismiss={pending}
      />

      {conflict && (
        <div className="space-y-4 px-6 py-5">
          <p className="flex items-start gap-3 text-sm text-text-secondary">
            <TriangleAlert
              className="mt-0.5 h-5 w-5 shrink-0 text-status-correction"
              aria-hidden="true"
            />
            {error.message}
          </p>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={onReload}
              className="inline-flex min-h-10 items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              Reload application
            </button>
          </div>
        </div>
      )}

      {forbidden && (
        <div className="space-y-4 px-6 py-5">
          <p className="flex items-start gap-3 text-sm text-text-secondary">
            <TriangleAlert
              className="mt-0.5 h-5 w-5 shrink-0 text-status-rejected"
              aria-hidden="true"
            />
            {error.message}
          </p>
          <p className="flex items-start gap-3 text-sm text-text-secondary">
            The page will update to show the current state.
          </p>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border-default bg-surface-card px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {showForm && (
        <div className="px-6 py-5">
          <p className="text-sm text-text-secondary">{config.hint}</p>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit(comment);
            }}
          >
            <div className="mt-4">
              <label
                htmlFor="decision-comment"
                className="mb-1.5 block text-sm font-medium text-text-primary"
              >
                {config.commentLabel}
              </label>
              <Textarea
                id="decision-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                maxLength={1000}
                aria-invalid={Boolean(commentError)}
                aria-describedby={
                  commentError ? "decision-comment-error" : undefined
                }
                placeholder={
                  config.commentRequired
                    ? "Briefly explain your decision…"
                    : "Optional note for the employee…"
                }
              />
              <div className="mt-1 flex items-center justify-between">
                <p
                  id="decision-comment-error"
                  role="alert"
                  className="text-sm text-status-rejected"
                >
                  {commentError}
                </p>
                <p
                  className="ml-auto text-xs text-text-muted"
                  aria-hidden="true"
                >
                  {comment.length}/1000
                </p>
              </div>
            </div>

            {error && error.kind !== "field" && (
              <p
                role="alert"
                aria-live="polite"
                className="mt-3 flex items-start gap-2 text-sm text-status-rejected"
              >
                <TriangleAlert
                  className="mt-0.5 h-4 w-4 shrink-0"
                  aria-hidden="true"
                />
                {error.message}
              </p>
            )}

            <div className="mt-5 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={pending}
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-border-default bg-surface-card px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={pending || (config.commentRequired && !comment.trim())}
                className={cn(
                  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
                  config.confirmClass
                )}
              >
                {pending ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : action === "approve" ? (
                  <Check className="h-4 w-4" aria-hidden="true" />
                ) : action === "return_for_correction" ? (
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <X className="h-4 w-4" aria-hidden="true" />
                )}
                {config.confirmLabel}
              </button>
            </div>
          </form>
        </div>
      )}
    </Dialog>
  );
}