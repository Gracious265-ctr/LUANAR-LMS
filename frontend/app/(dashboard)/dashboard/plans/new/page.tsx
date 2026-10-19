"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { CreatePlanForm } from "@/components/plans/CreatePlanForm";
import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

/**
 * Reads an optional `?leaveType=` so "plan a new one" from a missed plan lands
 * with the same leave type already chosen. `useSearchParams` must sit inside a
 * Suspense boundary for the route to stay prerenderable.
 */
function CreatePlanFields() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("leaveType");
  const parsed = raw === null ? Number.NaN : Number(raw);
  const initialLeaveType = Number.isFinite(parsed) ? parsed : undefined;
  return <CreatePlanForm initialLeaveType={initialLeaveType} />;
}

/** Create a Plan (spec 3.5). */
export default function NewPlanPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <Suspense
        fallback={
          <SkeletonRegion label="Loading the plan form">
            <Skeleton className="h-64 w-full rounded-xl" />
          </SkeletonRegion>
        }
      >
        <CreatePlanFields />
      </Suspense>
    </div>
  );
}
