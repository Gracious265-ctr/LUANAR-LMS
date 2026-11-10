"use client";

import { useRouter } from "next/navigation";

import { BalanceSection } from "@/components/leave/BalanceSection";
import { DashboardStatCards } from "@/components/leave/DashboardStatCards";
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
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
          <div className="space-y-3">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-48 w-full rounded-xl" />
          </div>
        </div>
        <div className="space-y-3 lg:col-start-2 lg:row-start-1">
          <Skeleton className="h-6 w-32" />
          <div className="flex flex-wrap gap-6">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-44 w-40 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
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
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
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
        /* Two columns from `lg` up: the figures the employee acts on — what is
           pending, what came back to them, what they submitted — fill the main
           column, and the balances sit in a rail beside them so the answer to
           "how much leave do I have left" is visible without scrolling past the
           lists. Below `lg` there is no rail, so the blocks simply stack in
           reading order: figures, anything needing attention, balances, history.
           Placement is explicit rather than DOM order in the wide layout, which
           is why the balance block is written after the sections it sits beside. */
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
          <div className="lg:col-start-1 lg:row-start-1">
            <DashboardStatCards
              pendingCount={data.pending_count}
              upcoming={data.upcoming_leave}
            />
          </div>

          {data.needs_attention.length > 0 && (
            <div className="lg:col-start-1">
              <NeedsAttentionSection applications={data.needs_attention} />
            </div>
          )}

          <div className="lg:col-start-2 lg:row-start-1">
            <BalanceSection balances={data.balances} />
          </div>

          <div className="lg:col-start-1">
            <RecentApplicationsSection applications={data.recent} />
          </div>
        </div>
      )}
    </div>
  );
}
