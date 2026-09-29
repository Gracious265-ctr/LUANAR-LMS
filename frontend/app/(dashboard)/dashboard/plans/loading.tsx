import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <SkeletonRegion label="Loading plans" className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-5 w-96 max-w-full" />
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle">
        <Skeleton className="h-5 w-56" />
        <div className="mt-4 space-y-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
          >
            <Skeleton className="h-5 w-40" />
            <Skeleton className="mt-2 h-4 w-52" />
            <Skeleton className="mt-4 h-10 w-full" />
          </div>
        ))}
      </div>
    </SkeletonRegion>
  );
}