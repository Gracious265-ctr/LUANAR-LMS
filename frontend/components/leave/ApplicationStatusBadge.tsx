import { Badge } from "@/components/ui/badge";
import { STATUS_META } from "@/lib/tracking/labels";
import type { LeaveApplicationStatus } from "@/lib/leave-dashboard";

/**
 * Status pill for a dashboard application row. The five approval statuses
 * reuse the app-wide `STATUS_META` labels/tones; `draft` is dashboard-only
 * (a draft never reaches the tracking timeline) so it carries its own muted
 * "Draft" tone.
 */
export function ApplicationStatusBadge({
  status,
}: {
  status: LeaveApplicationStatus;
}) {
  if (status === "draft") {
    return (
      <Badge tone="draft" size="sm">
        Draft
      </Badge>
    );
  }
  const meta = STATUS_META[status];
  return (
    <Badge tone={meta.badgeTone} size="sm">
      {meta.label}
    </Badge>
  );
}
