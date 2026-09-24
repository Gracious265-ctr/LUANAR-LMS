"use client";

import { CalendarX2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { actionLabel, blockedReasonLabel } from "@/lib/cancellations/labels";
import {
  fetchCancellationHistory,
  fetchEligibility,
} from "@/lib/cancellations/service";
import type {
  CancellationEligibility,
  CancellationRequest,
  SubmitCancellationResult,
} from "@/lib/cancellations/types";
import type { ApplicationSummary } from "@/lib/tracking/types";

import { CancelApplicationDialog } from "./cancel-application-dialog";
import { CancellationCard } from "./cancellation-card";

export interface CancellationSectionProps {
  applicationId: string;
  application: ApplicationSummary;
  onApplicationChanged: () => void;
}

/**
 * Unit 18 employee surface on the tracking page: a header action button driven
 * by the backend ``cancellation_action`` plus the cancellation card. Eligibility
 * and history are refetched after every mutation so the UI always reflects the
 * server (no optimistic updates, per spec 3.9).
 */
export function CancellationSection({
  applicationId,
  application,
  onApplicationChanged,
}: CancellationSectionProps) {
  const [eligibility, setEligibility] = useState<CancellationEligibility | null>(null);
  const [requests, setRequests] = useState<CancellationRequest[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [loadKey, setLoadKey] = useState(0);

  const reload = useCallback(() => setLoadKey((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [eligibilityResult, historyResult] = await Promise.all([
        fetchEligibility(applicationId),
        fetchCancellationHistory(applicationId),
      ]);
      if (cancelled) return;
      if (eligibilityResult.ok) {
        setEligibility(eligibilityResult.data);
      } else {
        setEligibility(null);
      }
      if (historyResult.ok) {
        setRequests(historyResult.data.results);
      } else {
        setRequests([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applicationId, loadKey]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  function handleSubmitted(result: SubmitCancellationResult & { ok: true }) {
    setDialogOpen(false);
    setToast(
      result.kind === "withdrawal"
        ? "Application withdrawn."
        : "Cancellation request submitted."
    );
    reload();
    onApplicationChanged();
  }

  function handleActionChanged(freshEligibility: CancellationEligibility) {
    setEligibility(freshEligibility);
    setDialogOpen(false);
    setToast("This request changed. Refreshing…");
    reload();
    onApplicationChanged();
  }

  if (!eligibility && requests.length === 0) {
    return null;
  }

  const action = eligibility?.cancellation_action ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-3">
        {action ? (
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground transition-colors hover:bg-button-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <CalendarX2 className="h-4 w-4" aria-hidden="true" />
            {actionLabel(action)}
          </button>
        ) : (
          eligibility?.cancellation_blocked_reason && (
            <p className="text-xs text-text-muted">
              {blockedReasonLabel(eligibility.cancellation_blocked_reason)}
            </p>
          )
        )}
      </div>

      {requests.length > 0 && <CancellationCard requests={requests} />}

      {dialogOpen && eligibility && action && (
        <CancelApplicationDialog
          action={action}
          eligibility={eligibility}
          application={application}
          onClose={() => setDialogOpen(false)}
          onSubmitted={handleSubmitted}
          onActionChanged={handleActionChanged}
        />
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-surface-card px-4 py-2.5 text-sm font-medium text-text-primary shadow-lg"
        >
          <CalendarX2 className="h-4 w-4 text-brand-primary" aria-hidden="true" />
          {toast}
        </div>
      )}
    </div>
  );
}