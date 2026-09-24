"use client";

import { useEffect, useState } from "react";

import {
  Ban,
  Check,
  ClipboardCheck,
  Loader2,
  ShieldAlert,
  TriangleAlert,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { ApiError } from "@/lib/approvals/service";
import { formatFinancialYear } from "@/lib/cancellation/format";
import {
  NOTIFICATION_LABEL,
  REQUEST_STATUS_LABEL,
} from "@/lib/cancellation/labels";
import {
  submitCancellationDecision,
} from "@/lib/cancellation/service";
import { useCancellationApprovalDetail } from "@/lib/cancellation/hooks";
import type {
  CancellationApprovalDetail,
  MyCancellationDecision,
} from "@/lib/cancellation/types";
import { formatDateTime } from "@/lib/tracking/format";

import { Card } from "../approvals/primitives";
import { Dialog, DialogHeader } from "../ui/dialog";
import { Textarea } from "../ui/textarea";
import { CancellationStageStepper } from "./CancellationStageStepper";

const MAX_COMMENT = 1000;

type DecisionError =
  | { kind: "field"; message: string; commentError?: string }
  | { kind: "inline"; message: string };

/**
 * Approver panel for a cancellation request, shown at the top of the Unit 16
 * review page when ``?cancellation={requestId}`` resolves to a request the
 * viewer is assigned to. Approve and Reject each require confirmation; Reject
 * requires a comment. A ``409`` produces a "changed, refreshing" toast then
 * refetches; a ``403`` flips the panel into read-only mode.
 */
export function CancellationDecisionPanel({
  requestId,
  onRefetch,
}: {
  requestId: string;
  onRefetch: () => void;
}) {
  const { state, refetch } = useCancellationApprovalDetail(requestId);
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<DecisionError | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  if (state.status === "loading") {
    return (
      <div className="h-48 animate-pulse rounded-xl bg-surface-muted" />
    );
  }

  if (state.status === "not_found") {
    return (
      <PanelCard title="Cancellation request">
        <p className="text-sm text-text-secondary">
          This cancellation request could not be found.
        </p>
      </PanelCard>
    );
  }

  if (state.status === "error") {
    return (
      <PanelCard title="Cancellation request">
        <p className="text-sm text-text-secondary">{state.message}</p>
      </PanelCard>
    );
  }

  const detail = state.data;
  const decided = detail.status !== "pending";
  const currentPendingStage = [...detail.stages]
    .sort((a, b) => a.order - b.order)
    .find((stage) => stage.status === "pending");
  const canAct = detail.can_act && !readOnly;
  const approveBlocked = canAct && (detail.leave_started || false);

  function openDialog(action: "approve" | "reject") {
    setError(null);
    setComment("");
    setDialog(action);
  }

  async function handleConfirm() {
    if (!dialog || pending) return;
    const trimmed = comment.trim();
    if (dialog === "reject" && trimmed.length === 0) {
      setError({
        kind: "field",
        message: "A comment is required for rejections.",
        commentError: "A comment is required for rejections.",
      });
      return;
    }
    if (trimmed.length > MAX_COMMENT) {
      setError({
        kind: "field",
        message: `The comment must be at most ${MAX_COMMENT} characters.`,
        commentError: `The comment must be at most ${MAX_COMMENT} characters.`,
      });
      return;
    }

    setPending(true);
    setError(null);
    try {
      await submitCancellationDecision(detail.id, {
        decision: dialog,
        comment: trimmed,
        stage_version: detail.stage_version,
      });
      setDialog(null);
      setComment("");
      refetch();
      onRefetch();
    } catch (err) {
      handleError(err);
    } finally {
      setPending(false);
    }
  }

  function handleError(err: unknown) {
    if (err instanceof ApiError && err.status === 409) {
      setToast("This request changed. Refreshing…");
      setDialog(null);
      refetch();
      onRefetch();
      return;
    }
    if (err instanceof ApiError && err.status === 403) {
      setReadOnly(true);
      setDialog(null);
      setError(null);
      refetch();
      onRefetch();
      return;
    }
    if (err instanceof ApiError && err.status === 400) {
      setError(parseFieldError(err.data));
      return;
    }
    setError({
      kind: "inline",
      message:
        "Something went wrong while saving your decision. Please try again.",
    });
  }

  const myDecision = detail.my_decision;

  return (
    <>
      <section
        aria-label="Cancellation request"
        className="space-y-6"
      >
        <PanelCard title="Cancellation request">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <RequestStatusBadge status={detail.status} />
            <span className="text-xs text-text-muted">
              Requested {formatDateTime(detail.requested_at)}
            </span>
          </div>

          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium text-text-muted">Requester</dt>
              <dd className="text-text-primary">Owning employee</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-text-muted">Reason</dt>
              <dd className="mt-1 rounded-lg bg-surface-subtle px-3 py-2 text-text-primary break-words whitespace-pre-line">
                {detail.reason}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-text-muted">
                Original leave
              </dt>
              <dd className="text-text-primary">
                {detail.application.leave_type} ·{" "}
                {formatPreviewDate(detail.application.start_date)} –{" "}
                {formatPreviewDate(detail.application.end_date)} ·{" "}
                {detail.application.working_days}{" "}
                {detail.application.working_days === 1 ? "day" : "days"}
              </dd>
            </div>
          </dl>

          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border-default pt-3">
            <p className="text-sm text-text-secondary">Balance impact</p>
            <p className="text-sm font-medium text-text-primary">
              {Number(detail.balance_impact.restores_days) > 0
                ? `Approving restores ${detail.balance_impact.restores_days} ${
                    Number(detail.balance_impact.restores_days) === 1
                      ? "day"
                      : "days"
                  } to ${formatFinancialYear(detail.balance_impact.financial_year)}`
                : "No annual leave balance impact"}
            </p>
          </div>

          {detail.stages.length > 0 && (
            <CancellationStageStepper
              stages={detail.stages}
              className="mt-5"
            />
          )}

          <p className="mt-4 border-t border-border-default pt-3 text-xs text-text-muted">
            Outcome notification:{" "}
            {NOTIFICATION_LABEL[detail.employee_notification_state]}
          </p>
        </PanelCard>

        {detail.leave_started && !decided && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-xl border border-status-rejected/30 bg-status-rejected-subtle px-4 py-3 text-sm text-status-rejected"
          >
            <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
            Leave has started; this request can only be rejected.
          </div>
        )}

        <PanelCard
          title="Decision"
        >
          {myDecision ? (
            <div className="space-y-2">
              <DecisionReadonly myDecision={myDecision} />
            </div>
          ) : canAct ? (
            <div>
              <p className="text-sm text-text-secondary">
                Your stage:{" "}
                <span className="font-medium text-text-primary">
                  {currentPendingStage?.role_label}
                </span>
              </p>
              <p className="mt-1 text-sm text-text-secondary">
                {approveBlocked
                  ? "The leave has started, so this request can only be rejected."
                  : "Decision required at your stage."}
              </p>
              <div className="mt-4 space-y-3">
                <button
                  type="button"
                  onClick={() => openDialog("approve")}
                  disabled={approveBlocked}
                  title={
                    approveBlocked
                      ? "The leave has already started."
                      : undefined
                  }
                  className={cn(
                    BUTTON_BASE,
                    "w-full bg-status-approved text-white hover:bg-status-approved/90",
                    approveBlocked && "cursor-not-allowed"
                  )}
                >
                  <Check className="h-4 w-4" aria-hidden="true" />
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => openDialog("reject")}
                  className={cn(
                    BUTTON_BASE,
                    "w-full border border-status-rejected bg-transparent text-status-rejected hover:bg-status-rejected-subtle"
                  )}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                  Reject
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3">
              <ShieldAlert
                className="mt-0.5 h-5 w-5 shrink-0 text-text-secondary"
                aria-hidden="true"
              />
              <p className="text-sm text-text-secondary">
                You are viewing this cancellation request in read-only mode —
                it is not your turn to decide.
              </p>
            </div>
          )}
        </PanelCard>
      </section>

      {dialog && (
        <Dialog
          open
          onClose={pending ? () => {} : () => setDialog(null)}
          labelledBy={undefined}
          ariaLabel={
            dialog === "approve"
              ? "Confirm approval"
              : "Confirm rejection"
          }
          blockDismiss={pending}
        >
          <DialogHeader
            titleId="cancellation-confirm-dialog-title"
            title={
              dialog === "approve"
                ? "Approve cancellation?"
                : "Reject cancellation?"
            }
            subtitle={
              dialog === "approve"
                ? "This will cancel the leave and restore the deducted days."
                : "The leave stays approved and the balance is untouched."
            }
            onClose={pending ? () => {} : () => setDialog(null)}
            blockDismiss={pending}
          />
          <div className="space-y-4 px-6 py-5">
            {dialog === "reject" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label
                    htmlFor="cancellation-comment"
                    className="text-sm font-medium text-text-primary"
                  >
                    Comment
                  </label>
                  <span
                    className={cn(
                      "text-xs tabular-nums",
                      comment.trim().length > MAX_COMMENT
                        ? "font-semibold text-status-rejected"
                        : "text-text-muted"
                    )}
                  >
                    {comment.trim().length}/{MAX_COMMENT}
                  </span>
                </div>
                <Textarea
                  id="cancellation-comment"
                  value={comment}
                  onChange={(event) => {
                    setComment(event.target.value);
                    if (error?.kind === "field") setError(null);
                  }}
                  placeholder="Explain why you are rejecting this request…"
                  disabled={pending}
                  aria-invalid={Boolean(
                    error?.kind === "field" && error.commentError
                  )}
                />
                {error?.kind === "field" && error.commentError && (
                  <p
                    role="alert"
                    className="flex items-start gap-1.5 text-sm text-status-rejected"
                  >
                    <TriangleAlert
                      className="mt-0.5 h-4 w-4 shrink-0"
                      aria-hidden="true"
                    />
                    {error.commentError}
                  </p>
                )}
              </div>
            )}

            {dialog === "approve" && (
              <p className="text-sm text-text-secondary">
                Optional comment for the record:
              </p>
            )}

            {dialog === "approve" && (
              <Textarea
                id="cancellation-approve-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Add an optional comment…"
                disabled={pending}
              />
            )}

            {error && !(error.kind === "field" && error.commentError) && (
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
                onClick={() => setDialog(null)}
                disabled={pending}
                className="inline-flex min-h-11 items-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={pending}
                className={cn(
                  BUTTON_BASE,
                  dialog === "approve"
                    ? "bg-status-approved text-white hover:bg-status-approved/90"
                    : "border border-status-rejected bg-status-rejected text-white hover:bg-status-rejected/90"
                )}
              >
                {pending && (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                )}
                {dialog === "approve"
                  ? "Yes, approve cancellation"
                  : "Yes, reject cancellation"}
              </button>
            </div>
          </div>
        </Dialog>
      )}

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-status-correction px-4 py-3 text-sm font-semibold text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </>
  );
}

const BUTTON_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

function PanelCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card title={title} icon={<ClipboardCheck className="h-4 w-4" />}>
      {children}
    </Card>
  );
}

function RequestStatusBadge({
  status,
}: {
  status: CancellationApprovalDetail["status"];
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-status-pending-subtle px-3 py-1 text-xs font-semibold text-status-pending">
      <Ban className="h-3.5 w-3.5" aria-hidden="true" />
      {REQUEST_STATUS_LABEL[status]}
    </span>
  );
}

function DecisionReadonly({
  myDecision,
}: {
  myDecision: MyCancellationDecision;
}) {
  return (
    <>
      <p className="text-sm text-text-secondary">
        You already decided on this request.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
            myDecision.action === "approved"
              ? "bg-status-approved-subtle text-status-approved"
              : "bg-status-rejected-subtle text-status-rejected"
          )}
        >
          {myDecision.action === "approved" ? "Approved" : "Rejected"}
        </span>
        {myDecision.decided_at && (
          <time dateTime={myDecision.decided_at} className="text-xs text-text-muted">
            {formatDateTime(myDecision.decided_at)}
          </time>
        )}
      </div>
      {myDecision.comment && (
        <p className="mt-3 rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
          {myDecision.comment}
        </p>
      )}
    </>
  );
}

function parseFieldError(data: unknown): DecisionError {
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (record.comment && Array.isArray(record.comment) && record.comment.length) {
      return {
        kind: "field",
        message: "Please fix the errors below before continuing.",
        commentError: String(record.comment[0]),
      };
    }
    if (typeof record.detail === "string") {
      return { kind: "field", message: record.detail };
    }
  }
  return {
    kind: "field",
    message: "The decision could not be saved. Check the form and try again.",
  };
}

function formatPreviewDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}