"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import type { ValidationIssue } from "@/lib/leave-validation";
import { Alert } from "@/components/ui/alert";

interface ValidationPanelProps {
  issues: ValidationIssue[];
  /** When true the panel shows a short "checking" state. */
  isLoading?: boolean;
  /** Green "all checks passed" line shown when valid and no issues. */
  isValid?: boolean;
  /** Network/other failure shown inline as a dismissible alert. */
  error?: string | null;
  onDismissError?: () => void;
  onRetry?: () => void;
  /** React 19 ref onto the active panel node (used to focus errors). */
  ref?: React.Ref<HTMLDivElement> | null;
}

/**
 * Renders backend-authored validation issues (red alert), a green pass line, or
 * an inline network failure. The whole region is polite-live for screen readers.
 */
export function ValidationPanel({
  issues,
  isLoading = false,
  isValid = false,
  error = null,
  onDismissError,
  onRetry,
  ref,
}: ValidationPanelProps) {
  if (error) {
    return (
      <Alert ref={ref} tone="rejected" className="border border-border-error p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 text-sm text-status-rejected">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="text-xs font-medium text-text-link hover:text-text-link-hover"
              >
                Retry
              </button>
            )}
            {onDismissError && (
              <button
                type="button"
                onClick={onDismissError}
                aria-label="Dismiss alert"
                className="text-xs font-medium text-text-muted hover:text-text-primary"
              >
                Dismiss
              </button>
            )}
          </div>
        </div>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <div ref={ref} className="rounded-lg border border-border-default bg-surface-muted p-4 flex items-center gap-2 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking your application...
      </div>
    );
  }

  if (issues.length > 0) {
    return (
      <Alert
        ref={ref}
        tone="rejected"
        tabIndex={-1}
        aria-live="polite"
        className="flex-col gap-0 border border-border-error p-4 outline-none"
      >
        <p className="text-sm font-semibold text-status-rejected mb-2">
          Your application has {issues.length === 1 ? "a problem" : `${issues.length} problems`}:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          {issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`} className="text-sm text-status-rejected">
              {issue.message}
            </li>
          ))}
        </ul>
      </Alert>
    );
  }

  if (isValid) {
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        className="rounded-lg border border-brand-secondary-border bg-brand-secondary-subtle p-4 flex items-center gap-2 text-sm text-brand-secondary"
      >
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        All checks passed — you can submit this application.
      </div>
    );
  }

  return null;
}