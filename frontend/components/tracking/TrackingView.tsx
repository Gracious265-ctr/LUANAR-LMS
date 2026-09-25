"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { CancellationSection } from "@/components/cancellations/cancellation-section";
import { ApprovedDocumentCard } from "@/components/documents/approved-document-card";
import { fetchTracking } from "@/lib/tracking/service";
import type { TrackingResult } from "@/lib/tracking/types";

import { ActivityTimeline } from "./ActivityTimeline";
import { ApprovalStepper } from "./ApprovalStepper";
import { CurrentStatusCard } from "./CurrentStatusCard";
import { OutcomePanel } from "./OutcomePanel";
import { ResubmissionNote } from "./ResubmissionNote";
import { SupportingDocumentsCard } from "./supporting-documents-card";
import { TrackingError } from "./TrackingError";
import { TrackingHeader } from "./TrackingHeader";
import { TrackingSkeleton } from "./TrackingSkeleton";

export function TrackingView({ applicationId }: { applicationId: string }) {
  const [result, setResult] = useState<TrackingResult | null>(() => null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const load = useCallback(
    async (mode: "mount" | "refresh") => {
      if (mode === "refresh") setRefreshing(true);
      else setLoading(true);
      const next = await fetchTracking(applicationId);
      setResult(next);
      if (next.ok) setLastRefreshed(new Date());
      if (mode === "refresh") setRefreshing(false);
      else setLoading(false);
    },
    [applicationId]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next = await fetchTracking(applicationId);
      if (cancelled) return;
      setResult(next);
      if (next.ok) setLastRefreshed(new Date());
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  if (loading) {
    return <TrackingSkeleton />;
  }

  if (!result || !result.ok) {
    if (!result) {
      return (
        <TrackingError
          message="Something went wrong."
          onRetry={() => load("mount")}
        />
      );
    }
    if (result.kind === "not_found") {
      return (
        <NotFoundState
          title="Application not found"
          message="This link may be out of date, or the application no longer exists."
        />
      );
    }
    if (result.kind === "not_submitted") {
      return (
        <NotFoundState
          title="This application is still a draft"
          message="Applications are tracked only after they have been submitted."
          actionHref={`/dashboard/leave/${encodeURIComponent(applicationId)}/edit`}
          actionLabel="Open draft"
        />
      );
    }
    return (
      <TrackingError message={result.message} onRetry={() => load("mount")} />
    );
  }

  const data = result.data;
  const showAttention =
    Boolean(data.rejection) || Boolean(data.correction);

  // Only mount the cancellation surface when the tracking payload carries the
  // Unit 18 fields (older fixtures without them must not trigger extra calls).
  const hasCancellationFields =
    data.cancellation_action !== undefined ||
    data.cancellation_blocked_reason !== undefined ||
    data.has_open_cancellation_request === true ||
    data.latest_cancellation !== undefined;

  return (
    <div className="space-y-6">
      <TrackingHeader
        data={data}
        onRefresh={() => load("refresh")}
        refreshing={refreshing}
        lastRefreshed={lastRefreshed}
      />

      {hasCancellationFields && (
        <CancellationSection
          applicationId={applicationId}
          application={data.application}
          onApplicationChanged={() => load("refresh")}
        />
      )}

      {data.documents !== undefined && (
        <SupportingDocumentsCard
          applicationId={applicationId}
          documents={data.documents}
        />
      )}

      {/* The official document only exists once the leave is approved, so the
          card is mounted only then rather than issuing a request that must
          404 for every other status. */}
      {data.status === "approved" && (
        <ApprovedDocumentCard applicationId={applicationId} />
      )}

      <CurrentStatusCard data={data} />

      <div className="flex flex-col gap-6 lg:flex-row-reverse">
        <div className="space-y-6 lg:w-1/3">
          {(showAttention || data.resubmission.count > 0) && (
            <div className="space-y-6">
              {showAttention && <OutcomePanel data={data} />}
              {data.resubmission.count > 0 && (
                <ResubmissionNote resubmission={data.resubmission} />
              )}
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-6">
          <ApprovalStepper data={data} />
          <ActivityTimeline data={data} />
        </div>
      </div>
    </div>
  );
}

function NotFoundState({
  title,
  message,
  actionHref,
  actionLabel,
}: {
  title: string;
  message: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center">
      <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
      <p className="mx-auto mt-2 max-w-md text-sm break-words text-text-secondary">
        {message}
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/dashboard/leave/drafts"
          className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border-default bg-surface-card px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          My applications
        </Link>
        {actionHref && actionLabel && (
          <Link
            href={actionHref}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            {actionLabel}
          </Link>
        )}
      </div>
    </div>
  );
}