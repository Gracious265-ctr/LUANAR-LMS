"use client";

import { CalendarX2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { actionLabel, blockedReasonLabel } from "@/lib/cancellations/labels";
import {
  fetchCancellationHistory,
  fetchEligibility,
} from "@/lib/cancellations/service";
import type {
  CancellationAction,
  CancellationEligibility,
  CancellationRequest,
  SubmitCancellationResult,
} from "@/lib/cancellations/types";
import type { ApplicationSummary } from "@/lib/tracking/types";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

import { CancelApplicationDialog } from "./cancel-application-dialog";
import { CancellationCard } from "./cancellation-card";

export interface CancellationSectionProps {
  applicationId: string;
  application: ApplicationSummary;
  onApplicationChanged: () => void;
}

/**
 * Unit 18 employee surface on the tracking page: a header action button driven
 * by the backend ``cancellation_action`` plus the cancellation card. The button
 * disappears the moment the request is dispatched (spec 3.5 optimistic update)
 * and comes back — with an error toast — if the backend refuses; eligibility
 * and history are refetched after every mutation so the final state is the
 * server's.
 */
export function CancellationSection({
  applicationId,
  application,
  onApplicationChanged,
}: CancellationSectionProps) {
  const [eligibility, setEligibility] = useState<CancellationEligibility | null>(null);
  const [requests, setRequests] = useState<CancellationRequest[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  // The action the dialog was opened with, held separately so the optimistic
  // eligibility patch below can hide the page button without closing the
  // dialog that is still mid-flight.
  const [openAction, setOpenAction] = useState<CancellationAction | null>(null);
  const [loadKey, setLoadKey] = useState(0);
  const { showToast } = useToast();
  const eligibilitySnapshotRef = useRef<CancellationEligibility | null>(null);

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

  function handleSubmitted(result: SubmitCancellationResult & { ok: true }) {
    setDialogOpen(false);
    setOpenAction(null);
    eligibilitySnapshotRef.current = null;
    showToast(
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
    setOpenAction(null);
    eligibilitySnapshotRef.current = null;
    showToast("This request changed. Refreshing…", "info");
    reload();
    onApplicationChanged();
  }

  // Hides the page's action button while the request is in flight; the dialog
  // keeps its own `openAction` so it stays mounted over the patched state.
  function handleOptimistic() {
    eligibilitySnapshotRef.current = eligibility;
    setEligibility((prev) =>
      prev ? { ...prev, cancellation_action: null } : prev
    );
  }

  function handleRollback(message: string) {
    if (eligibilitySnapshotRef.current) {
      setEligibility(eligibilitySnapshotRef.current);
      eligibilitySnapshotRef.current = null;
    }
    showToast(message, "error");
  }

  if (!eligibility && requests.length === 0) {
    return null;
  }

  const action = eligibility?.cancellation_action ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-3">
        {action ? (
          <Button
            type="button"
            onClick={() => {
              setOpenAction(action);
              setDialogOpen(true);
            }}
            variant="primary"
            className="min-h-11"
          >
            <CalendarX2 className="h-4 w-4" aria-hidden="true" />
            {actionLabel(action)}
          </Button>
        ) : (
          eligibility?.cancellation_blocked_reason && (
            <p className="text-xs text-text-muted">
              {blockedReasonLabel(eligibility.cancellation_blocked_reason)}
            </p>
          )
        )}
      </div>

      {requests.length > 0 && <CancellationCard requests={requests} />}

      {dialogOpen && eligibility && openAction && (
        <CancelApplicationDialog
          action={openAction}
          eligibility={eligibility}
          application={application}
          onClose={() => {
            setDialogOpen(false);
            setOpenAction(null);
          }}
          onOptimistic={handleOptimistic}
          onRollback={handleRollback}
          onSubmitted={handleSubmitted}
          onActionChanged={handleActionChanged}
        />
      )}
    </div>
  );
}