"use client";

import { useRouter } from "next/navigation";
import { CalendarDays, Clock } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { formatDateRange } from "@/lib/date";
import type { UpcomingLeave } from "@/lib/leave-dashboard";

/** "in 5 days", with today/singular handled so the figure always reads well. */
function daysLabel(daysUntil: number): string {
  if (daysUntil === 0) return "Today";
  if (daysUntil === 1) return "in 1 day";
  return `in ${daysUntil} days`;
}

/**
 * The two figures the employee checks first: how much of their leave is still
 * waiting on a decision, and when their next approved leave begins. Each card
 * is one click from the place it describes — pending, filtered to that status;
 * upcoming, straight to the application's tracking page.
 */
export function DashboardStatCards({
  pendingCount,
  upcoming,
}: {
  pendingCount: number;
  upcoming: UpcomingLeave | null;
}) {
  const router = useRouter();

  const upcomingDetail = upcoming
    ? [formatDateRange(upcoming.start_date, upcoming.end_date), upcoming.leave_type]
        .filter(Boolean)
        .join(", ")
    : "No upcoming leave scheduled";

  return (
    <div className="grid grid-cols-2 gap-4">
      <StatCard
        title="Pending Applications"
        value={String(pendingCount)}
        subtitle="awaiting review"
        icon={<Clock className="h-5 w-5" />}
        variant="pending"
        onClick={() => router.push("/dashboard/leave/drafts?status=submitted")}
      />
      <StatCard
        title="Upcoming Leave"
        value={upcoming ? daysLabel(upcoming.days_until) : "—"}
        subtitle={upcomingDetail}
        icon={<CalendarDays className="h-5 w-5" />}
        variant="primary"
        onClick={
          upcoming ? () => router.push(`/applications/${upcoming.id}`) : undefined
        }
      />
    </div>
  );
}
