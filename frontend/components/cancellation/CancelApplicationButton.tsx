"use client";

import { useState } from "react";

import { SquareMinus, TriangleAlert } from "lucide-react";

import { BLOCKED_REASON_TEXT } from "@/lib/cancellation/labels";
import type { CancellationEligibility } from "@/lib/cancellation/types";
import type { ApplicationSummary } from "@/lib/tracking/types";

import { CancelApplicationDialog } from "./CancelApplicationDialog";

/**
 * Header action for the tracking page. The label follows the backend-provided
 * ``cancellation_action``; when it is ``null`` the button is hidden and a muted
 * explanatory line (from ``cancellation_blocked_reason``) is shown instead.
 */
export function CancelApplicationButton({
  application,
  eligibility,
  onSuccess,
}: {
  application: Pick<
    ApplicationSummary,
    | "id"
    | "reference_number"
    | "leave_type"
    | "start_date"
    | "end_date"
    | "working_days"
  >;
  eligibility: Pick<
    CancellationEligibility,
    | "cancellation_action"
    | "cancellation_blocked_reason"
    | "estimated_restoration_days"
  >;
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const { cancellation_action: action, cancellation_blocked_reason: blocked } =
    eligibility;

  if (!action) {
    if (!blocked) return null;
    return (
      <p className="flex items-center gap-1.5 text-xs text-text-muted">
        <TriangleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {BLOCKED_REASON_TEXT[blocked] ?? "This application cannot be cancelled."}
      </p>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={
          "inline-flex min-h-11 items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 " +
          (action === "withdraw"
            ? "border border-status-rejected bg-transparent text-status-rejected hover:bg-status-rejected-subtle"
            : "bg-brand-primary text-white hover:bg-brand-primary-hover")
        }
      >
        <SquareMinus className="h-4 w-4" aria-hidden="true" />
        {action === "withdraw" ? "Withdraw application" : "Request cancellation"}
      </button>
      <CancelApplicationDialog
        open={open}
        onClose={() => setOpen(false)}
        application={application}
        eligibility={eligibility}
        onSuccess={onSuccess}
      />
    </>
  );
}