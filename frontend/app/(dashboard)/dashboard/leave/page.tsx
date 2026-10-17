"use client";

import { useRouter } from "next/navigation";

import { BalanceSection } from "@/components/leave/BalanceSection";
import { DashboardStatCards } from "@/components/leave/DashboardStatCards";
import { DraftsSection } from "@/components/leave/DraftsSection";
import { NeedsAttentionSection } from "@/components/leave/NeedsAttentionSection";
import { RecentApplicationsSection } from "@/components/leave/RecentApplicationsSection";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useLeaveDashboard } from "@/lib/hooks/useLeaveDashboard";

/** Laid out like the real page so loading never shifts the content below it. */
function DashboardSkeleton() {
  return (
    <SkeletonRegion label="Loading your leave dashboard" className="space-y-8">
      <div className="grid grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
      <div className="space-y-3">
        <Skeleton className="h-6 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-6">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-44 w-40 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
    </SkeletonRegion>
  );
}

export default function LeaveDashboardPage() {
  const { data, isLoading, error, refetch } = useLeaveDashboard();
  const router = useRouter();

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Leave Applications
          </h1>
          <p className="text-text-muted">Welcome back</p>
        </div>
        <Button
          variant="primary"
          onClick={() => router.push("/dashboard/leave/drafts?compose=1")}
        >
          + New Application
        </Button>
      </div>

      {isLoading && <DashboardSkeleton />}

      {error && !isLoading && (
        <ErrorState
          title="Couldn't load your dashboard"
          message={error}
          onRetry={refetch}
          retryLabel="Retry"
        />
      )}

      {data && (
        <>
          <DashboardStatCards
            pendingCount={data.pending_count}
            upcoming={data.upcoming_leave}
          />

          {data.needs_attention.length > 0 && (
            <NeedsAttentionSection applications={data.needs_attention} />
          )}

          <BalanceSection balances={data.balances} />

          {data.drafts.length > 0 && <DraftsSection drafts={data.drafts} />}

          <RecentApplicationsSection applications={data.recent} />
        </>
      )}
    </div>
  );
}
