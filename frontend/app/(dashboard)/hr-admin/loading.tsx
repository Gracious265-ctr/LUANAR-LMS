import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

/**
 * Mirrors `app/(dashboard)/hr-admin/page.tsx`: heading followed by a
 * three-column grid of ten navigation tiles.
 */
export default function Loading() {
  return (
    <SkeletonRegion label="Loading HR administration" className="space-y-6">
      <div>
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-2 h-5 w-96 max-w-full" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 11 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
          >
            <Skeleton className="mb-3 size-9 rounded-lg" />
            <Skeleton className="h-7 w-36" />
            <div className="mt-1 space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <Skeleton className="h-5 w-full" />
      </div>
    </SkeletonRegion>
  );
}
