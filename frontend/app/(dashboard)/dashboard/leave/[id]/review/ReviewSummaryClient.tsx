"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";

import { type LeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import {
  type ValidationIssue,
  submitApplication,
  SubmitError,
} from "@/lib/leave-validation";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { LeaveReviewSummary } from "@/components/leave/leave-review-summary";
import { BalanceCard } from "@/components/leave/balance-card";
import { ValidationPanel } from "@/components/leave/validation-panel";
import { Alert } from "@/components/ui/alert";

type NetworkError = {
  message: string;
};

export function ReviewSummaryClient({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [leaveTypeName, setLeaveTypeName] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [panelIssues, setPanelIssues] = useState<ValidationIssue[]>([]);
  const [submitError, setSubmitError] = useState<NetworkError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [focusSignal, setFocusSignal] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const isSubmittingRef = useRef(false);

  const validation = useLeaveValidation(
    {
      leave_type_id: application?.leave_type_id ?? null,
      start_date: application?.start_date ?? null,
      end_date: application?.end_date ?? null,
      draft_id: applicationId,
    },
    { enabled: Boolean(application) }
  );

  useEffect(() => {
    Promise.all([getLeaveApplication(applicationId), getLeaveTypes()])
      .then(([app, types]) => {
        setApplication(app);
        const match = types.find((t) => t.id === app.leave_type_id);
        setLeaveTypeName(match?.name || `Type #${app.leave_type_id}`);
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : "Failed to load application")
      );
  }, [applicationId]);

  useEffect(() => {
    if (focusSignal === 0) return;
    panelRef.current?.focus();
  }, [focusSignal]);

  if (loadError) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-8 text-center">
        <p className="text-status-rejected text-sm">{loadError}</p>
      </div>
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
  const issues = panelIssues.length > 0 ? panelIssues : (result?.errors ?? []);
  const showBalance = result?.available_balance !== null && result?.available_balance !== undefined;
  const submitDisabled =
    validation.isLoading ||
    issues.length > 0 ||
    submitting ||
    !result?.valid;

  const handleSubmit = async () => {
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setSubmitting(true);
    setSubmitError(null);
    setPanelIssues([]);
    try {
      await submitApplication(application.id);
      router.push(`/dashboard/leave/${application.id}/submitted`);
    } catch (err) {
      if (err instanceof SubmitError) {
        if (err.status === 422) {
          setPanelIssues(err.errors);
          setFocusSignal((n) => n + 1);
        } else if (err.status === 409 && err.code === "ALREADY_SUBMITTED") {
          router.push(`/dashboard/leave/${application.id}/submitted`);
        } else {
          setSubmitError({ message: err.message });
        }
      } else {
        setSubmitError({
          message: err instanceof Error ? err.message : "Failed to submit application",
        });
      }
    } finally {
      isSubmittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <LinkBack href={`/dashboard/leave/${application.id}/edit`} label="Back to draft" />
        <h1 className="text-xl font-semibold tracking-tight text-text-primary">
          Review your application
        </h1>
      </div>

      <LeaveReviewSummary
        application={application}
        leaveTypeName={leaveTypeName}
        validation={result}
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
              issues={issues}
              isLoading={validation.isLoading}
              isValid={Boolean(result?.valid)}
              error={validation.error}
              onRetry={() => {
                setSubmitError(null);
              }}
              onDismissError={() => {
                setSubmitError(null);
              }}
            />

      {submitError && (
        <Alert
          tone="rejected"
          className="items-start justify-between gap-3 border border-border-error p-4"
        >
          <div className="flex items-start gap-2 text-sm text-status-rejected">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{submitError.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setSubmitError(null)}
            className="text-xs font-medium text-text-muted hover:text-text-primary shrink-0"
          >
            Dismiss
          </button>
        </Alert>
      )}

      <div className="flex justify-end gap-3">
        <LinkBack
          href={`/dashboard/leave/${application.id}/edit`}
          label="Back to edit"
          button
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitDisabled}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-md bg-brand-secondary text-brand-secondary-foreground font-medium text-sm hover:bg-brand-secondary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            "Submit application"
          )}
        </button>
      </div>
    </div>
  );
}

function LinkBack({
  href,
  label,
  button,
}: {
  href: string;
  label: string;
  button?: boolean;
}) {
  return (
    <Link
      href={href}
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