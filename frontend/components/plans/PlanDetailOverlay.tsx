"use client";

import { Calendar } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/states";
import { formatDateRange } from "@/lib/date";
import { PLAN_STATUS_META } from "@/lib/plans/labels";
import type { LeavePlan } from "@/lib/plans/types";

/**
 * The day popover on the Team Plans calendar (spec 3.6).
 *
 * Read-only by design: a plan is a personal intention, so the only person who
 * can act on it is its owner, and the action belongs on My Plans — not buried in
 * someone else's calendar.
 */
export function PlanDetailOverlay({
  date,
  plans,
  onClose,
}: {
  /** The day being inspected, `yyyy-mm-dd`. */
  date: string | null;
  plans: LeavePlan[];
  onClose: () => void;
}) {
  return (
    <Dialog open={date !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent aria-describedby="plan-day-description">
        <DialogHeader>
          <DialogTitle>{date ? formatDateRange(date, date) : ""}</DialogTitle>
          <DialogDescription id="plan-day-description">
            Planned leave on this day.
          </DialogDescription>
        </DialogHeader>

        {plans.length === 0 ? (
          <EmptyState
            icon={<Calendar className="h-8 w-8 text-text-muted" />}
            title="Nothing planned"
            description="No one in your scope has planned leave on this day."
          />
        ) : (
          <ul className="space-y-3">
            {plans.map((plan) => {
              const meta = PLAN_STATUS_META[plan.status];
              return (
                <li
                  key={plan.id}
                  className="rounded-lg border border-border-default p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-text-primary">
                      {plan.employee_name}
                    </span>
                    <span className="text-sm text-text-secondary">
                      {plan.leave_type_name}
                    </span>
                    <Badge tone={meta.badgeTone} size="sm">
                      {meta.label}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-text-muted">
                    {formatDateRange(plan.planned_start_date, plan.planned_end_date)}
                  </div>
                  {plan.notes && (
                    <p className="mt-2 line-clamp-2 text-sm text-text-secondary">
                      {plan.notes}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
