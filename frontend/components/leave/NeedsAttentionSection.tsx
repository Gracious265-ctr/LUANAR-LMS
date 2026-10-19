"use client";

import { useRouter } from "next/navigation";

import { ApplicationStatusBadge } from "@/components/leave/ApplicationStatusBadge";
import { cardStyles } from "@/components/ui/card";
import { formatDateRange } from "@/lib/date";
import type { LeaveApplicationSummary } from "@/lib/leave-dashboard";
import { cn } from "@/lib/utils";

/**
 * Applications the employee has to act on (rejected back to them). Cards route
 * straight into the edit overlay — the whole point of
 * the section is getting the employee back to a place they can resubmit, so
 * this is the one card that must not detour through the read-only tracking
 * page first.
 */
export function NeedsAttentionSection({
  applications,
}: {
  applications: LeaveApplicationSummary[];
}) {
  const router = useRouter();

  return (
    <section aria-labelledby="needs-attention-heading">
      <h2
        id="needs-attention-heading"
        className="mb-3 text-lg font-semibold text-text-primary"
      >
        Needs Your Attention
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {applications.map((app) => (
          <button
            key={app.id}
            type="button"
            onClick={() =>
              router.push(`/dashboard/leave/drafts?edit=${app.id}`)
            }
            className={cn(cardStyles, "hover-float focus-ring w-full p-4 text-left")}
          >
            <ApplicationStatusBadge status={app.status} />
            <div className="mt-2 font-medium text-text-primary">
              {app.leave_type ?? "Leave application"}
            </div>
            <div className="text-sm text-text-muted">
              {formatDateRange(app.start_date, app.end_date)}
            </div>
            {app.last_comment_excerpt && (
              <p className="mt-2 line-clamp-2 text-sm text-text-secondary">
                “{app.last_comment_excerpt}”
              </p>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}
