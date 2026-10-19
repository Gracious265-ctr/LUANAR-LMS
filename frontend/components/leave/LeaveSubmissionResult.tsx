"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { type LeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { SubmissionConfirmation } from "@/components/leave/submission-confirmation";
import { Card } from "@/components/ui/card";

export interface LeaveSubmissionResultProps {
  applicationId: string;
  /**
   * When provided the confirmation renders a single "Done" action instead of
   * links, so the overlay does not navigate away underneath itself.
   */
  onDone?: () => void;
  /**
   * Called when the application turns out not to be submitted.
   *
   * Defaults to doing nothing, which leaves the in-dialog message in place.
   * That is the safe default: redirecting here would tear down a dialog that is
   * showing a legitimate result. Only the standalone page, which has no dialog
   * to preserve, opts into a redirect.
   */
  onNotSubmitted?: () => void;
}

export function LeaveSubmissionResult({
  applicationId,
  onDone,
  onNotSubmitted,
}: LeaveSubmissionResultProps) {
  const router = useRouter();
  const resolvedDone = onDone ?? (() => router.push("/dashboard/leave/drafts"));
  // No-op by default, so an un-submitted application leaves the confirmation
  // message on screen rather than navigating out from under the caller.
  const resolvedNotSubmitted = onNotSubmitted ?? (() => {});
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [leaveTypeName, setLeaveTypeName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notSubmitted, setNotSubmitted] = useState(false);

  // The caller may pass a fresh callback each render, so the redirect is
  // read through a ref and the fetch is keyed only on the application id.
  const notSubmittedRef = useRef(resolvedNotSubmitted);

  useEffect(() => {
    notSubmittedRef.current = resolvedNotSubmitted;
  });

  useEffect(() => {
    let active = true;
    Promise.all([getLeaveApplication(applicationId), getLeaveTypes()])
      .then(([app, types]) => {
        if (!active) return;
        if (app.status !== "submitted" || !app.reference_number) {
          setNotSubmitted(true);
          notSubmittedRef.current();
          return;
        }
        setApplication(app);
        const match = types.find((t) => t.id === app.leave_type_id);
        setLeaveTypeName(match?.name || `Type #${app.leave_type_id}`);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : "Failed to load application"
        );
      });
    return () => {
      active = false;
    };
  }, [applicationId]);

  if (notSubmitted) {
    return (
      <p className="text-sm text-text-muted py-8 text-center">
        This application has not been submitted.
      </p>
    );
  }

  if (error) {
    return (
      <Card className="text-center">
        <p className="text-status-rejected text-sm">{error}</p>
      </Card>
    );
  }

  if (!application) {
    return <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />;
  }

  return (
    <SubmissionConfirmation
      application={{
        id: application.id,
        reference_number: application.reference_number,
        status: application.status,
        submitted_at: application.submitted_at,
        working_days: application.working_days,
        calendar_days: application.calendar_days,
        leave_type: { id: application.leave_type_id ?? 0 },
        start_date: application.start_date,
        end_date: application.end_date,
      }}
      leaveTypeName={leaveTypeName}
      onDone={resolvedDone}
    />
  );
}

/**
 * Standalone confirmation page, kept for direct links. Redirects to review
 * when the application is not actually submitted, which a hard reload or a
 * stale link can produce. This is the one caller that wants the redirect, since
 * there is no dialog whose state a navigation would destroy.
 */
export function SubmittedClient({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  return (
    <LeaveSubmissionResult
      applicationId={applicationId}
      onNotSubmitted={() =>
        router.replace(`/dashboard/leave/${applicationId}/review`)
      }
    />
  );
}
