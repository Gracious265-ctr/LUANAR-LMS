/**
 * Loading state: header block, status card and four stage placeholders.
 * The only animation in the whole feature, and it respects reduced motion.
 */
export function TrackingSkeleton() {
  return (
    <div
      aria-label="Loading application tracking"
      aria-busy="true"
      className="space-y-6"
    >
      <div className="space-y-4">
        <div className="h-6 w-1/3 max-w-56 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
        <div className="flex items-center gap-4">
          <div className="h-7 w-48 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
          <div className="h-6 w-36 animate-pulse rounded-full bg-surface-muted motion-safe:animate-pulse" />
        </div>
        <div className="h-4 w-64 max-w-full animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
        <div className="h-4 w-48 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
      </div>

      <div className="h-28 rounded-xl border border-border-default bg-surface-card p-5">
        <div className="h-5 w-52 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
        <div className="mt-3 h-4 w-72 max-w-full animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-5">
        <div className="mb-4 h-5 w-40 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="mb-4 flex gap-3 last:mb-0">
            <div className="h-7 w-7 animate-pulse rounded-full bg-surface-muted motion-safe:animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-40 animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
              <div className="h-3 w-64 max-w-full animate-pulse rounded bg-surface-muted motion-safe:animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}