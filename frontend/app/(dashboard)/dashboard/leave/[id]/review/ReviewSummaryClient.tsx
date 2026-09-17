"use client";

import { useEffect, useState } from "react";

import { type LeaveApplication, getLeaveApplication } from "@/lib/leave-api";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { ReviewSummary } from "@/components/leave/ReviewSummary";

export function ReviewSummaryClient({ applicationId }: { applicationId: string }) {
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [leaveTypeName, setLeaveTypeName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getLeaveApplication(applicationId),
      getLeaveTypes(),
    ])
      .then(([app, types]) => {
        setApplication(app);
        const match = types.find((t) => t.id === app.leave_type_id);
        setLeaveTypeName(match?.name || `Type #${app.leave_type_id}`);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-surface-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-surface-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-8 text-center">
        <p className="text-status-rejected text-sm">{error}</p>
      </div>
    );
  }

  if (!application) return null;

  return <ReviewSummary application={application} leaveTypeName={leaveTypeName} />;
}
