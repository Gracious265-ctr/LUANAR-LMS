"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { type LeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { SubmissionConfirmation } from "@/components/leave/submission-confirmation";

export function SubmittedClient({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [leaveTypeName, setLeaveTypeName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    Promise.all([getLeaveApplication(applicationId), getLeaveTypes()])
      .then(([app, types]) => {
        // Anything that is not actually submitted goes back to the review
        // screen so a hard reload or direct navigation stays coherent.
        if (app.status !== "submitted" || !app.reference_number) {
          setRedirecting(true);
          router.replace(`/dashboard/leave/${applicationId}/review`);
          return;
        }
        setApplication(app);
        const match = types.find((t) => t.id === app.leave_type_id);
        setLeaveTypeName(match?.name || `Type #${app.leave_type_id}`);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load application")
      );
  }, [applicationId, router]);

  if (redirecting) {
    return (
      <p className="text-sm text-text-muted py-8 text-center">
        This application has not been submitted — taking you back...
      </p>
    );
  }

  if (error) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-8 text-center">
        <p className="text-status-rejected text-sm">{error}</p>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
    );
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
        leave_type: {
          id: application.leave_type_id ?? 0,
        },
        start_date: application.start_date,
        end_date: application.end_date,
      }}
      leaveTypeName={leaveTypeName}
    />
  );
}