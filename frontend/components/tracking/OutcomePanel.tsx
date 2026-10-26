"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import { acceptRejection } from "@/lib/tracking/service";
import type { TrackingResponse } from "@/lib/tracking/types";
import { STATUS_BORDER, STATUS_STYLES, STATUS_TEXT } from "@/lib/status-styles";

/**
 * Attention panel: rejection details with the two exits from a rejection —
 * edit & resubmit, or accept it and close the application. Once accepted the
 * actions are gone and the panel records when the employee closed it.
 */
export function OutcomePanel({
  data,
  onAccepted,
}: {
  data: TrackingResponse;
  onAccepted?: () => void;
}) {
  const outcome = data.rejection;
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!outcome) return null;

  const accent = STATUS_STYLES.rejected;
  const resubmission = data.resubmission;
  const accepted = Boolean(outcome.accepted_at);

  async function confirm() {
    setBusy(true);
    setError("");
    const result = await acceptRejection(data.application.id);
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setConfirming(false);
    onAccepted?.();
  }

  return (
    <section
      aria-label="Rejection details"
      className={cn(
        "rounded-xl border bg-surface-card p-5 shadow-subtle",
        STATUS_BORDER.rejected
      )}
    >
      <div className={cn("flex items-center gap-2", STATUS_TEXT.rejected)}>
        <AlertCircle className="h-5 w-5" aria-hidden="true" />
        <h2 className="text-base font-semibold text-text-primary">
          Rejection details
        </h2>
      </div>

      <dl className="mt-4 space-y-3 text-sm">
        <div>
          <dt className="text-xs font-medium text-text-muted">Stage</dt>
          <dd className="break-words text-text-primary">
            Stage {outcome.stage_order} · {outcome.role_label}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">Approver</dt>
          <dd className="break-words text-text-primary">
            {outcome.approver_name}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">Decision</dt>
          <dd className="text-text-primary">
            <time dateTime={outcome.decided_at}>
              {formatDateTime(outcome.decided_at)}
            </time>
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-text-muted">Reason</dt>
          <dd
            className={cn(
              "mt-1 rounded-lg border-l-2 px-3 py-2 break-words whitespace-pre-line",
              accent
            )}
          >
            {outcome.reason}
          </dd>
        </div>
      </dl>

      {accepted ? (
        <p className="mt-4 text-sm text-text-secondary">
          Rejection accepted on{" "}
          <time dateTime={outcome.accepted_at ?? undefined}>
            {outcome.accepted_at
              ? formatDateTime(outcome.accepted_at)
              : ""}
          </time>
          .
        </p>
      ) : (
        <>
          <p className="mt-4 text-sm font-medium text-text-secondary">
            Workflow stopped.
          </p>

          {resubmission.returns_to_stage && (
            <p className="mt-4 text-sm break-words text-text-secondary">
              When you resubmit, this application returns to{" "}
              <strong>{resubmission.returns_to_stage.role_label}</strong>.
            </p>
          )}

          {error && (
            <Alert tone="rejected" className="mt-4">
              {error}
            </Alert>
          )}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            {resubmission.can_resubmit && (
              <Link
                href={`/dashboard/leave/${data.application.id}/edit`}
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-ring"
              >
                Edit &amp; resubmit
              </Link>
            )}
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border-default bg-surface-card px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-ring"
            >
              Accept rejection
            </button>
          </div>
        </>
      )}

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Accept this rejection?</AlertDialogTitle>
            <AlertDialogDescription>
              The application closes. You will not be able to edit or resubmit
              it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy}
              onClick={(event) => {
                // Keep the dialog open while the request runs, and only close
                // it once the server has recorded the acceptance. Radix closes
                // on click by default, so the action is prevented and the
                // dialog dismissed from `confirm` on success.
                event.preventDefault();
                void confirm();
              }}
            >
              {busy ? "Accepting…" : "Accept rejection"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
