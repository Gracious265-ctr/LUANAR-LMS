import { cn } from "@/lib/utils";

import { STATUS_META } from "@/lib/tracking/labels";
import type { TrackingStatus } from "@/lib/tracking/types";

/**
 * Always icon + text; status is never conveyed by color alone.
 */
export function StatusBadge({
  status,
  className,
}: {
  status: TrackingStatus;
  className?: string;
}) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </span>
  );
}