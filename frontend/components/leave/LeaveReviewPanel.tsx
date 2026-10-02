"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";

import { type LeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { type ValidationIssue } from "@/lib/leave-validation";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { useSubmitLeaveApplication } from "@/lib/hooks/useSubmitLeaveApplication";
import { LeaveReviewSummary } from "@/components/leave/leave-review-summary";
import { BalanceCard } from "@/components/leave/balance-card";
import { ValidationPanel } from "@/components/leave/validation-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export interface LeaveReviewPanelProps {
  applicationId: string;
  /** Fired after a successful submit, or when the server says it already was. */
  onSubmitted: (applicationId: string) => void;
  /**
   * Overrides the default "back to edit" links so the compose overlay can step
   * back to its own form stage instead of navigating away.
   */
  onEdit?: () => void;
  /** Hides the page-level "Back to draft" link; the overlay has no page to return to. */
  showBackLink?: boolean;
}

/**
 * The review step of a leave application, shared by the standalone review page
 * and the compose overlay.
 *
 * Working days always come from the server: either the live validation result
 * or, while that is pending or blocked, the application's stored
 * `calculated_days`. They are never recomputed client-side.
 */
export function LeaveReviewPanel({
  applicationId,
  onSubmitted,
  onEdit,
  showBackLink = true,
}: LeaveReviewPanelProps) {
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [leaveTypeName, setLeaveTypeName] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const validation = useLeaveValidation(
    {
      leave_type_id: application?.leave_type_id ?? null,
      start_date: application?.start_date ?? null,
      end_date: application?.end_date ?? null,
      draft_id: applicationId,
    },
    { enabled: Boolean(application) }
  );

  const {
    submit,
    isSubmitting,
    issues,
    failure,
    dismissFailure,
  } = useSubmitLeaveApplication({
    onSubmitted: () => onSubmitted(applicationId),
    onAlreadySubmitted: () => onSubmitted(applicationId),
  });

  useEffect(() => {
    Promise.all([getLeaveApplication(applicationId), getLeaveTypes()])
      .then(([app, types]) => {
        setApplication(app);
        const match = types.find((t) => t.id === app.leave_type_id);
        setLeaveTypeName(match?.name || `Type #${app.leave_type_id}`);
      })
      .catch((err: unknown) =>
        setLoadError(
          err instanceof Error ? err.message : "Failed to load application"
        )
      );
  }, [applicationId]);

  // A 422 replaces the panel's issues without moving the user, so focus is
  // pulled to the panel to announce the new content to screen readers.
  useEffect(() => {
    if (issues.length === 0) return;
    panelRef.current?.focus();
  }, [issues]);

  const handleSubmit = async () => {
    await submit(applicationId);
  };

  if (loadError) {
    return (
      <Card className="text-center">
        <p className="text-status-rejected text-sm">{loadError}</p>
      </Card>
    );
  }

  if (!application) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-surface-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
      </div>
    );
  }

  const result = validation.result;
  const shownIssues: ValidationIssue[] =
    issues.length > 0 ? issues : (result?.errors ?? []);
  const showBalance =
    result?.available_balance !== null && result?.available_balance !== undefined;
  const submitDisabled =
    validation.isLoading ||
    shownIssues.length > 0 ||
    isSubmitting ||
    !result?.valid;

  return (
    <div className="space-y-6">
      {showBackLink && (
        <div className="flex items-center gap-3">
          <BackToEdit
            onEdit={onEdit}
            applicationId={applicationId}
            label="Back to draft"
          />
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            Review your application
          </h1>
        </div>
      )}

      <LeaveReviewSummary
        application={application}
        leaveTypeName={leaveTypeName}
        validation={result}
        onEdit={onEdit}
      />

      {showBalance && (
        <BalanceCard
          availableBalance={result?.available_balance ?? null}
          balanceAfter={result?.balance_after_if_approved ?? null}
          financialYear={result?.financial_year ?? null}
        />
      )}

      <ValidationPanel
        ref={panelRef}
        issues={shownIssues}
        isLoading={validation.isLoading}
        isValid={Boolean(result?.valid)}
        error={validation.error}
        onRetry={dismissFailure}
        onDismissError={dismissFailure}
      />

      {failure && (
        <Alert
          tone="rejected"
          className="items-start justify-between gap-3 border border-border-error p-4"
        >
          <div className="flex items-start gap-2 text-sm text-status-rejected">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{failure.message}</span>
          </div>
          <Button
            type="button"
            onClick={dismissFailure}
            variant="link"
            size="sm"
            className="h-auto shrink-0 text-text-muted hover:no-underline"
          >
            Dismiss
          </Button>
        </Alert>
      )}

      <div className="flex justify-end gap-3">
        <BackToEdit
          onEdit={onEdit}
          applicationId={applicationId}
          label="Back to edit"
          button
        />
        <Button
          type="button"
          onClick={handleSubmit}
          disabled={submitDisabled}
          variant="primary"
          size="lg"
          className="bg-brand-secondary text-brand-secondary-foreground border-transparent hover:bg-brand-secondary-hover"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            "Submit application"
          )}
        </Button>
      </div>
    </div>
  );
}

/**
 * Renders as a link on the standalone review page and as a button when the
 * overlay supplies `onEdit`, so the overlay never triggers a navigation.
 */
function BackToEdit({
  onEdit,
  applicationId,
  label,
  button,
}: {
  onEdit?: () => void;
  applicationId: string;
  label: string;
  button?: boolean;
}) {
  if (onEdit) {
    return (
      <button
        type="button"
        onClick={onEdit}
        className={
          button
            ? "inline-flex items-center gap-1.5 px-4 py-2.5 rounded-md border border-input-border bg-input-background text-sm font-medium text-text-primary hover:bg-surface-hover transition-colors"
            : "inline-flex items-center gap-1.5 text-sm font-medium text-text-link hover:text-text-link-hover"
        }
      >
        <ArrowLeft className="h-4 w-4" />
        {label}
      </button>
    );
  }

  return (
    <Link
      href={`/dashboard/leave/${applicationId}/edit`}
      className={
        button
          ? "inline-flex items-center gap-1.5 px-4 py-2.5 rounded-md border border-input-border bg-input-background text-sm font-medium text-text-primary hover:bg-surface-hover transition-colors"
          : "inline-flex items-center gap-1.5 text-sm font-medium text-text-link hover:text-text-link-hover"
      }
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Link>
  );
}
