import { AlertTriangle } from "lucide-react";

import { formatDate } from "@/lib/approvals/format";
import type { ConflictDay } from "@/lib/calendar/types";

/**
 * The inline warning beside Approve when the request under review would push a
 * day over the team's conflict cap (spec 3.2).
 *
 * It is informational here; the server enforces the same rule as a hard block,
 * and names the same day and headcount in its 409.
 */
export function ApprovalConflictNotice({
  conflict,
  teamSize,
}: {
  conflict: ConflictDay;
  teamSize: number;
}) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg border border-border-warning bg-amber-100/70 p-3 text-sm text-text-primary"
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
        aria-hidden="true"
      />
      <p>
        Approving this would mean{" "}
        <span className="font-semibold">{conflict.count}</span> of {teamSize}{" "}
        team members are out on {formatDate(conflict.day)}.
      </p>
    </div>
  );
}
