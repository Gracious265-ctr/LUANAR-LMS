import { AlertTriangle } from "lucide-react";

import { Alert } from "@/components/ui/alert";

/**
 * Inline error card for network/5xx failures with a retry action.
 */
export function TrackingError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <Alert
      tone="rejected"
      className="rounded-xl border border-status-rejected/30 p-5"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="mt-0.5 h-5 w-5 shrink-0 text-status-rejected"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-text-primary">
            Could not load tracking information
          </h2>
          <p className="mt-1 break-words text-sm text-text-secondary">
            {message}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            Try again
          </button>
        </div>
      </div>
    </Alert>
  );
}