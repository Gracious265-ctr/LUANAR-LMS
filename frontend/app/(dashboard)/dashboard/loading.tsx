import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

/**
 * Mirrors `app/(dashboard)/dashboard/page.tsx`: heading, four stat cards, the
 * employee record grid, then recent activity. The placeholder blocks are sized
 * to the real elements so the swap to loaded content does not shift the page.
 */
export default function Loading() {
  return (
    <SkeletonRegion label="Loading dashboard" className="space-y-6">
      <div>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-2 h-5 w-64" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <Skeleton className="mb-4 h-7 w-48" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="mb-1 h-4 w-24" />
              <Skeleton className="h-5 w-32" />
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <Skeleton className="mb-4 h-7 w-40" />
        <ul className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <li key={i} className="flex gap-3">
              <Skeleton className="mt-0.5 size-6 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <Skeleton className="h-5 w-52" />
                  <Skeleton className="h-4 w-28" />
                </div>
                <Skeleton className="mt-1 h-4 w-40" />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </SkeletonRegion>
  );
}

function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle">
      <div className="mb-3 flex items-center justify-between">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="size-9 rounded-lg" />
      </div>
      <Skeleton className="h-9 w-14" />
      <Skeleton className="mt-1 h-5 w-20" />
    </div>
  );
}
