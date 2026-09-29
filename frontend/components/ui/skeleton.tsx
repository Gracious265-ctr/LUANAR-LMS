import { cn } from "@/lib/utils";

/**
 * Base skeleton block. Mirrors the height of the real element it stands in
 * for so loading a list never shifts the layout.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "motion-safe:animate-pulse rounded bg-surface-muted",
        className
      )}
    />
  );
}

export function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-tight", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-1/2" : "w-full")}
        />
      ))}
    </div>
  );
}

/** Matches a real card: same radius, border and padding as `Card`. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle",
        className
      )}
    >
      <Skeleton className="mb-4 h-5 w-40" />
      <SkeletonText lines={3} />
    </div>
  );
}

/**
 * Matches a real table: one header row plus `rows` body rows, so the
 * placeholder occupies the same height as the loaded table (including
 * anything below it, such as a pagination bar).
 */
export function SkeletonTable({
  rows = 8,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-tight", className)} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-md border border-border-subtle bg-surface-card px-4 py-3"
        >
          <Skeleton className="size-8 rounded-full" />
          <Skeleton className="h-3.5 flex-1" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonList({
  count = 3,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-group", className)} aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
        >
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="mt-3 space-y-tight">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Loading region for a screen: announced once, laid out like real content. */
export function SkeletonRegion({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-label={label} aria-busy="true" className={className}>
      {children}
    </div>
  );
}
