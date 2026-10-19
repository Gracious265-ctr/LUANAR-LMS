import {
  Ban,
  Bell,
  CalendarClock,
  CalendarX,
  CheckCircle2,
  type LucideIcon,
} from "lucide-react";

import type { BadgeTone } from "@/components/ui/badge";
import type { LeavePlan, LeavePlanStatus } from "./types";

/**
 * Plan status → label, pill tone and icon.
 *
 * The tones are drawn from the app-wide status palette so a plan pill reads the
 * same way a leave pill does; `notified` maps to `pending` because a notified
 * plan is the one asking to be acted on, exactly as a pending application is.
 */
export const PLAN_STATUS_META: Record<
  LeavePlanStatus,
  { label: string; badgeTone: BadgeTone; icon: LucideIcon }
> = {
  upcoming: { label: "Upcoming", badgeTone: "info", icon: CalendarClock },
  notified: { label: "Ready to apply", badgeTone: "pending", icon: Bell },
  missed: { label: "Missed", badgeTone: "rejected", icon: CalendarX },
  converted: { label: "Converted", badgeTone: "approved", icon: CheckCircle2 },
  cancelled: { label: "Cancelled", badgeTone: "cancelled", icon: Ban },
};

export function planStatusLabel(status: LeavePlanStatus): string {
  return PLAN_STATUS_META[status]?.label ?? status;
}

/**
 * Whether the owner can still turn this plan into a draft.
 *
 * `converted`, `cancelled` and `missed` are finished states; `upcoming` and
 * `notified` are both live, so "Apply Now" is available from the moment the
 * plan exists, not only once a reminder has fired (spec 2.3).
 */
export function isActionable(plan: Pick<LeavePlan, "status">): boolean {
  return plan.status === "upcoming" || plan.status === "notified";
}

export function isHistory(plan: Pick<LeavePlan, "status">): boolean {
  return !isActionable(plan);
}

/**
 * Sort key for a plan within a section: soonest start date first, most recently
 * created as the tie-break, so the list is stable.
 */
export function planSortKey(plan: LeavePlan): [string, string] {
  return [plan.planned_start_date, plan.created_at];
}
