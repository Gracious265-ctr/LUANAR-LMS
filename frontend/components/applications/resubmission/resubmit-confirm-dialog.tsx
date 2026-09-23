"use client";

import { Loader2 } from "lucide-react";

import { Dialog, DialogHeader } from "@/components/ui/dialog";
import type { ResubmissionContext } from "@/lib/applications/resubmission-types";

import { ChangesSummary } from "./changes-summary";

/**
 * Confirmation dialog for the final resubmit: shows where the application
 * returns and a preview of the changes since the last submission.
 */
export function ResubmitConfirmDialog({
  open,
  context,
  busy,
  conflictMessage,
  onConfirm,
  onClose,
}: {
  open: boolean;
  context: ResubmissionContext | null;
  busy: boolean;
  conflictMessage: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  if (!context) return null;
  const { reference, returns_to, changes_preview } = context;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      labelledBy="resubmit-dialog-title"
      ariaLabel="Confirm resubmission"
      blockDismiss={busy}
    >
      <DialogHeader
        titleId="resubmit-dialog-title"
        title="Resubmit application"
        subtitle={reference}
        onClose={onClose}
        blockDismiss={busy}
      />

      <div className="space-y-4 px-6 py-4">
        {returns_to && (
          <p className="rounded-lg bg-surface-subtle px-3 py-2 text-sm text-text-secondary">
            On resubmission, this application returns to{" "}
            <strong className="font-medium text-text-primary">
              {returns_to.role_label}
            </strong>
            {returns_to.approver_name &&
              returns_to.approver_name !== returns_to.role_label && (
                <>
                  {" · "}
                  {returns_to.approver_name}
                </>
              )}
            .
          </p>
        )}

        <div>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">
            Changes since the last submission
          </h3>
          <ChangesSummary changes={changes_preview} compact />
        </div>

        {conflictMessage && (
          <div
            role="alert"
            className="rounded-lg border border-border-error bg-status-rejected-subtle p-3 text-sm text-status-rejected"
          >
            {conflictMessage}
          </div>
        )}
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-border-default px-6 py-4 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onClose}
          disabled={busy}
          className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {busy ? "Resubmitting…" : "Confirm resubmit"}
        </button>
      </div>
    </Dialog>
  );
}