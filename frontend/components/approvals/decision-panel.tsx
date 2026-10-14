"use client";

<<<<<<< HEAD
import { useState } from "react";

import Link from "next/link";
import { Check, ClipboardCheck, RotateCcw, ShieldAlert, X } from "lucide-react";

import { cn } from "@/lib/utils";

import { submitDecision, ApiError } from "@/lib/approvals/service";
import type {
  ApprovalDetail,
  ApprovalStage,
  DecisionAction,
} from "@/lib/approvals/types";

import { ActionBadge, Card, DecidedAt } from "./primitives";
import {
  DecisionDialog,
  type DecisionError,
} from "./decision-dialog";

const BUTTON_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

export function DecisionPanel({
  detail,
  onDecisionApplied,
  onConflict,
  onForbidden,
}: {
  detail: ApprovalDetail;
  onDecisionApplied: (updated: ApprovalDetail, action: DecisionAction) => void;
  onConflict: () => void;
  onForbidden: () => void;
}) {
  const [dialogAction, setDialogAction] = useState<DecisionAction | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<DecisionError | null>(null);

  const myStage = detail.my_stage_role_label;
  const myDecisions = detail.stages.filter(
    (stage): stage is ApprovalStage & { action: DecisionAction } =>
      stage.role_label === myStage && stage.action !== null
  );
  const myDecision = myDecisions[myDecisions.length - 1] ?? null;
  const canDecide = detail.permissions.can_decide;

  function openDialog(action: DecisionAction) {
    setError(null);
    setDialogAction(action);
  }

  async function handleSubmit(comment: string) {
    const action = dialogAction;
    if (!action || pending) return;
    const version = detail.current_stage?.version;
    if (typeof version !== "number") {
      setError({
        kind: "other",
        message: "This application is not open for decisions.",
      });
      return;
    }

    setPending(true);
    setError(null);
    try {
      const updated = await submitDecision(detail.id, {
        action,
        comment: comment.trim(),
        stage_version: version,
      });
      setDialogAction(null);
      onDecisionApplied(updated, action);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError({
            kind: "conflict",
            message:
              "This application has changed since you opened it. Reload to see the latest details before making a decision.",
          });
        } else if (err.status === 403) {
          setError({
            kind: "forbidden",
            message: "You can no longer decide on this application.",
          });
        } else if (err.status === 400) {
          setError(parseFieldError(err.data));
        } else {
          setError({
            kind: "other",
            message:
              "Something went wrong while saving your decision. Please try again.",
          });
        }
      } else {
        setError({
          kind: "other",
          message: "You are offline or the service is unavailable. Please try again.",
        });
      }
    } finally {
      setPending(false);
    }
  }

  function handleReload() {
    setDialogAction(null);
    onConflict();
  }

  function handleForbiddenClose() {
    setDialogAction(null);
    onForbidden();
  }

  return (
    <>
      <Card title="Decision" icon={<ClipboardCheck className="h-4 w-4" />}>
        {myDecision ? (
          <div>
            <div className="flex items-center gap-2">
              <ActionBadge action={myDecision.action} />
              <DecidedAt value={myDecision.decided_at ?? ""} />
            </div>
            {myDecision.comment && (
              <p className="mt-3 rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
                {myDecision.comment}
              </p>
            )}
            <p className="mt-4 border-t border-border-default pt-3 text-sm text-text-secondary">
              {detail.status === "pending"
                ? "No further action is required at your stage."
                : "No further action is required on this application."}
            </p>
            <Link
              href="/approvals"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary transition-colors hover:text-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
            >
              Return to approvals
            </Link>
          </div>
        ) : canDecide ? (
          <div>
            <p className="text-sm text-text-secondary">
              Your stage:{" "}
              <span className="font-medium text-text-primary">
                {detail.my_stage_role_label}
              </span>
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              Decision required at your stage.
            </p>
            <div className="mt-4 space-y-3">
              <button
                type="button"
                onClick={() => openDialog("approve")}
                className={cn(
                  BUTTON_BASE,
                  "w-full bg-status-approved text-white hover:bg-status-approved/90"
                )}
              >
                <Check className="h-4 w-4" aria-hidden="true" />
                Approve
              </button>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => openDialog("return_for_correction")}
                  className={cn(
                    BUTTON_BASE,
                    "bg-status-correction text-white hover:bg-status-correction/90"
                  )}
                >
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  Return
                </button>
                <button
                  type="button"
                  onClick={() => openDialog("reject")}
                  className={cn(
                    BUTTON_BASE,
                    "border border-status-rejected bg-transparent text-status-rejected hover:bg-status-rejected-subtle"
                  )}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                  Reject
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <ShieldAlert
              className="mt-0.5 h-5 w-5 shrink-0 text-text-secondary"
              aria-hidden="true"
            />
            <p className="text-sm text-text-secondary">
              {detail.permissions.reason ||
                "You are viewing this application in read-only mode."}
            </p>
          </div>
        )}
      </Card>

      {!myDecision && canDecide && (
        <nav
          aria-label="Decision actions"
          className="fixed inset-x-0 bottom-0 z-40 border-t border-border-default bg-surface-card px-4 py-3 shadow-lg lg:hidden"
        >
          <div className="mx-auto flex max-w-3xl items-stretch gap-3">
            <button
              type="button"
              onClick={() => openDialog("return_for_correction")}
              className={cn(BUTTON_BASE, "flex-1 bg-status-correction text-white")}
            >
              Return
            </button>
            <button
              type="button"
              onClick={() => openDialog("reject")}
              className={cn(
                BUTTON_BASE,
                "flex-1 border border-status-rejected bg-transparent text-status-rejected"
              )}
            >
              Reject
            </button>
            <button
              type="button"
              onClick={() => openDialog("approve")}
              className={cn(BUTTON_BASE, "flex-1 bg-status-approved text-white")}
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Approve
            </button>
          </div>
        </nav>
      )}

      {dialogAction && (
        <DecisionDialog
          open
          action={dialogAction}
          detail={detail}
          pending={pending}
          error={error}
          onClose={
            pending
              ? () => {}
              : () => {
                  if (error?.kind === "forbidden") {
                    handleForbiddenClose();
                  } else {
                    setDialogAction(null);
                  }
                }
          }
          onSubmit={handleSubmit}
          onReload={handleReload}
        />
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
    if (typeof record.action === "string") {
      return { kind: "field", message: record.action };
    }
  }
  return {
    kind: "field",
    message: "The decision could not be saved. Check the form and try again.",
  };
=======
import { Check, RotateCcw, X } from "lucide-react";

import { STATUS_META, restrictionLabel } from "@/lib/approvals/labels";
import { formatDateTime } from "@/lib/approvals/format";
import type { ApprovalAction, ApprovalReview } from "@/lib/approvals/types";
import { Button } from "@/components/ui/button";

import { Panel } from "./panel";

export interface DecisionPanelProps {
  data: ApprovalReview;
  onAction: (kind: ApprovalAction) => void;
  disabled?: boolean;
}

export function DecisionPanel({ data, onAction, disabled }: DecisionPanelProps) {
  if (!data.can_decide) {
    return (
      <Panel title="Decision">
        <p className="text-sm text-text-secondary">
          {restrictionLabel(
            data.decision_restriction,
            data.workflow.current_stage?.role_label ?? null,
            data.workflow.state
          )}
        </p>
        {data.my_decision && data.workflow.state !== "pending" && (
          <p className="mt-2 text-xs text-text-muted">
            You {decisionPastTense(data.my_decision.action)} this application on{" "}
            {formatDateTime(data.my_decision.decided_at)}.
          </p>
        )}
        {statusNote(data.workflow.state) && (
          <p className="mt-2 text-xs text-text-muted">{statusNote(data.workflow.state)}</p>
        )}
      </Panel>
    );
  }

  return (
    <Panel title="Decision">
      <div className="space-y-2.5">
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("approve")}
          variant="primary"
          size="lg"
          className="w-full"
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          Approve
        </Button>
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("reject")}
          variant="secondary"
          size="lg"
          className="w-full border-status-rejected bg-status-rejected-subtle text-status-rejected"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Reject
        </Button>
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onAction("return_for_correction")}
          variant="secondary"
          size="lg"
          className="w-full border-status-correction bg-status-correction-subtle text-status-correction"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Return for Correction
        </Button>
      </div>
    </Panel>
  );
}

function decisionPastTense(action: ApprovalAction): string {
  switch (action) {
    case "approve":
      return "approved";
    case "reject":
      return "rejected";
    case "return_for_correction":
      return "returned for correction";
  }
}

function statusNote(status: ApprovalReview["workflow"]["state"]): string | null {
  if (status === "cancelled") {
    return `Status: ${STATUS_META.cancelled.label.toLowerCase()}.`;
  }
  if (status === "rejected") {
    return "The workflow has stopped for this application.";
  }
  return null;
>>>>>>> feature/plans-teams
}