import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";

/**
 * Route-level loading compositions.
 *
 * The HR area repeats a handful of page shapes across ~30 routes, so the
 * skeletons live here once and each `loading.tsx` picks one. Every block is
 * sized to the element it replaces (a `py-3` table row, a `p-6` card, a
 * `text-2xl` heading) so the swap to loaded content does not shift the page.
 */

const CARD = "rounded-xl border border-border-default bg-surface-card shadow-subtle";

export function PageHeaderSkeleton({
  titleWidth = "w-40",
  subtitleWidth = "w-64",
  action = false,
}: {
  titleWidth?: string;
  subtitleWidth?: string;
  action?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <Skeleton className={`h-8 ${titleWidth}`} />
        <Skeleton className={`mt-2 h-5 ${subtitleWidth} max-w-full`} />
      </div>
      {action && <Skeleton className="h-10 w-36 shrink-0 rounded-control" />}
    </div>
  );
}

/** `space-y-6` wrapper every page in the app uses. */
export function PageSkeleton({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <SkeletonRegion label={label} className="space-y-6">
      {children}
    </SkeletonRegion>
  );
}

/** Heading + search form + table card, as used by every HR list route. */
export function ListPageSkeleton({
  label,
  titleWidth,
  subtitleWidth,
  rows = 8,
  columns = 4,
  withSearch = true,
  withAction = true,
}: {
  label: string;
  titleWidth?: string;
  subtitleWidth?: string;
  rows?: number;
  columns?: number;
  withSearch?: boolean;
  withAction?: boolean;
}) {
  return (
    <PageSkeleton label={label}>
      <PageHeaderSkeleton
        titleWidth={titleWidth}
        subtitleWidth={subtitleWidth}
        action={withAction}
      />
      {withSearch && (
        <div className="flex max-w-md items-center gap-2">
          <div className="relative flex-1">
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
          <Skeleton className="h-10 w-24 rounded-lg" />
        </div>
      )}
      <div className={`${CARD} overflow-hidden p-0`}>
        <div className="flex items-center gap-6 border-b border-border-default px-6 py-3">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton key={i} className="h-3 flex-1" />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, row) => (
          <div
            key={row}
            className="flex items-center gap-6 border-b border-border-default px-6 py-4 last:border-b-0"
          >
            {Array.from({ length: columns }).map((_, col) => (
              <Skeleton key={col} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </PageSkeleton>
  );
}

/** Back link + heading + form card, as used by the `new` and `edit` routes. */
export function FormPageSkeleton({
  label,
  titleWidth = "w-32",
  subtitleWidth = "w-96",
  fields = 6,
  withBack = true,
}: {
  label: string;
  titleWidth?: string;
  subtitleWidth?: string;
  fields?: number;
  withBack?: boolean;
}) {
  return (
    <PageSkeleton label={label}>
      <div>
        {withBack && <Skeleton className="h-5 w-40" />}
        <Skeleton className={`h-8 ${titleWidth} ${withBack ? "mt-2" : ""}`} />
        <Skeleton className={`mt-2 h-5 ${subtitleWidth} max-w-full`} />
      </div>
      <div className={`${CARD} p-6`}>
        <div className="space-y-5">
          {Array.from({ length: fields }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-10 w-full rounded-lg" />
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-2 border-t border-border-default pt-5">
          <Skeleton className="h-10 w-24 rounded-control" />
          <Skeleton className="h-10 w-32 rounded-control" />
        </div>
      </div>
    </PageSkeleton>
  );
}

/** Heading + a stacked record card, as used by the `[id]` detail routes. */
export function DetailPageSkeleton({
  label,
  titleWidth = "w-48",
  subtitleWidth = "w-64",
  fields = 8,
}: {
  label: string;
  titleWidth?: string;
  subtitleWidth?: string;
  fields?: number;
}) {
  return (
    <PageSkeleton label={label}>
      <PageHeaderSkeleton titleWidth={titleWidth} subtitleWidth={subtitleWidth} />
      <div className={`${CARD} p-6`}>
        <Skeleton className="mb-4 h-7 w-44" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: fields }).map((_, i) => (
            <div key={i}>
              <Skeleton className="mb-1 h-4 w-24" />
              <Skeleton className="h-5 w-32" />
            </div>
          ))}
        </div>
      </div>
    </PageSkeleton>
  );
}
