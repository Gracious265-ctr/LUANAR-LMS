import { Badge } from "@/components/ui/badge";
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
    <Badge tone={meta.badgeTone} className={className}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}
