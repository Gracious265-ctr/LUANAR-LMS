"use client";

import { CalendarPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PlanCard } from "@/components/plans/PlanCard";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";
import { EmptyPanel, ErrorState } from "@/components/ui/states";
import { usePlans } from "@/lib/hooks/usePlans";
import { isActionable } from "@/lib/plans/labels";
import type { LeavePlan } from "@/lib/plans/types";

/** By soonest start date, then most recently created — one ordering for all groups. */
function byStartDate(a: LeavePlan, b: LeavePlan) {
  if (a.planned_start_date !== b.planned_start_date) {
    return a.planned_start_date < b.planned_start_date ? -1 : 1;
  }
  return a.created_at < b.created_at ? -1 : 1;
}

function PlanSkeleton() {
  return (
    <SkeletonRegion label="Loading your plans" className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-40 rounded-xl" />
        ))}
      </div>
    </SkeletonRegion>
  );
}

/**
 * My Plans — the module's landing page (spec 3.4).
 *
 * Live plans (`upcoming` + `notified`) come first so the ones needing action are
 * above the fold; the finished ones sit below as history. Notified plans are the
 * ones a reminder has fired for, so they lead the live group by the same
 * soonest-start ordering.
 */
export function MyPlans() {
  const { data, isLoading, error, refetch } = usePlans();
  const router = useRouter();

  if (isLoading) return <PlanSkeleton />;

  if (error && !data) {
    return (
      <ErrorState
        title="Couldn't load your plans"
        message={error}
        onRetry={refetch}
        retryLabel="Retry"
      />
    );
  }

  const plans = data ?? [];
  if (plans.length === 0) {
    return (
      <EmptyPanel
        icon={<CalendarPlus className="h-10 w-10 text-brand-primary" />}
        title="No leave plans yet"
        description="Save a leave type and dates ahead of time."
        action={
          <Button variant="primary" onClick={() => router.push("/dashboard/plans/new")}>
            Create a Plan
          </Button>
        }
      />
    );
  }

  const live = plans.filter(isActionable).sort(byStartDate);
  const history = plans.filter((p) => !isActionable(p)).sort(byStartDate);

  return (
    <div className="space-y-8">
      {live.length > 0 && (
        <section aria-labelledby="live-plans-heading">
          <h2
            id="live-plans-heading"
            className="mb-3 text-lg font-semibold text-text-primary"
          >
            Planned leave
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {live.map((plan) => (
              <PlanCard key={plan.id} plan={plan} onCancel={() => refetch()} />
            ))}
          </div>
        </section>
      )}

      {history.length > 0 && (
        <section aria-labelledby="history-plans-heading">
          <h2
            id="history-plans-heading"
            className="mb-3 text-lg font-semibold text-text-primary"
          >
            Earlier plans
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {history.map((plan) => (
              <PlanCard key={plan.id} plan={plan} onCancel={() => refetch()} />
            ))}
          </div>
        </section>
      )}

      <div>
        <Link
          href="/dashboard/plans/new"
          className="inline-flex items-center gap-2 text-sm font-medium text-brand-primary hover:underline"
        >
          <CalendarPlus className="h-4 w-4" aria-hidden="true" />
          Create a Plan
        </Link>
      </div>
    </div>
  );
}
