"use client";

import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";

import { cardStyles } from "@/components/ui/card";
import { formatDateRange } from "@/lib/date";
import type { LeaveApplicationSummary } from "@/lib/leave-dashboard";
import { cn } from "@/lib/utils";

/**
 * In-progress applications (started but not yet submitted). Like the
 * needs-attention cards, clicking anywhere continues straight into the edit
 * overlay — resuming a draft is two clicks end to end (§2.5).
 */
export function DraftsSection({
  drafts,
}: {
  drafts: LeaveApplicationSummary[];
}) {
  const router = useRouter();

  return (
    <section aria-labelledby="drafts-heading">
      <h2
        id="drafts-heading"
        className="mb-3 text-lg font-semibold text-text-primary"
      >
        Continue a Draft
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {drafts.map((app) => (
          <button
            key={app.id}
            type="button"
            onClick={() =>
              router.push(`/dashboard/leave/drafts?edit=${app.id}`)
            }
            className={cn(cardStyles, "hover-float focus-ring w-full p-4 text-left")}
          >
            <div className="font-medium text-text-primary">
              {app.leave_type ?? "Untitled draft"}
            </div>
            {app.start_date && (
              <div className="text-sm text-text-muted">
                {formatDateRange(app.start_date, app.end_date)}
              </div>
            )}
            <div className="mt-2 text-xs text-text-muted">
              Last edited{" "}
              {formatDistanceToNow(new Date(app.updated_at), {
                addSuffix: true,
              })}
            </div>
            <span className="mt-3 inline-flex text-sm font-medium text-brand-primary">
              Continue →
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
