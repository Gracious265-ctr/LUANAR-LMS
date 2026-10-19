import { cn } from "@/lib/utils";

import type { BadgeTone } from "@/components/ui/badge";
import { badgeVariants } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/tracking/format";
import { eventIcon, eventTitle } from "@/lib/tracking/labels";
import type { TrackingResponse } from "@/lib/tracking/types";

const EVENT_ACCENT_TONE: Record<string, BadgeTone> = {
  approved: "approved",
  rejected: "rejected",
};

/**
 * Vertical timeline, newest first (the response already orders events that way;
 * this component renders them in the received order).
 */
export function ActivityTimeline({ data }: { data: TrackingResponse }) {
  const events = data.events;
  const stages = data.stages;

  if (events.length === 0) {
    return (
      <section
        aria-label="Activity history"
        className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
      >
        <h2 className="text-base font-semibold text-text-primary">
          Activity history
        </h2>
        <p className="mt-3 text-sm text-text-muted">No activity yet.</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Activity history"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <h2 className="mb-4 text-base font-semibold text-text-primary">
        Activity history
      </h2>
      <ol className="space-y-5">
        {events.map((event) => {
          const Icon = eventIcon(event.type);
          const accent = badgeVariants({
            tone: EVENT_ACCENT_TONE[event.type] ?? "muted",
          });
          return (
            <li key={event.id} className="flex gap-3">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                  accent
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm font-medium text-text-primary">
                  {eventTitle(event, stages)}
                </p>
                <p className="text-xs text-text-secondary">
                  {event.actor.name} · {event.actor.role_label}
                </p>
                <time
                  dateTime={event.occurred_at}
                  className="text-xs text-text-muted"
                >
                  {formatDateTime(event.occurred_at)}
                </time>
                {event.comment && (
                  <p className="mt-1 rounded-lg bg-surface-subtle px-3 py-2 text-sm break-words whitespace-pre-line text-text-secondary">
                    {event.comment}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}