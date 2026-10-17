"use client";

import { useState } from "react";
import {
  addDays,
  endOfMonth,
  format,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonRegion } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import { useTeamPlans } from "@/lib/hooks/useTeamPlans";
import { PLAN_STATUS_META } from "@/lib/plans/labels";
import type { LeavePlan } from "@/lib/plans/types";
import { PlanDetailOverlay } from "./PlanDetailOverlay";
import { ScopeSelector } from "./ScopeSelector";

/** A stable, low-saturation hue per leave type, so bars colour-code by type. */
function typeHue(leaveTypeId: number): string {
  const hue = (leaveTypeId * 47) % 360;
  return `hsl(${hue} 55% 45%)`;
}

function plansOnDay(plans: LeavePlan[], day: Date): LeavePlan[] {
  const iso = format(day, "yyyy-MM-dd");
  return plans.filter((p) => p.planned_start_date <= iso && iso <= p.planned_end_date);
}

/** One plan bar on a day cell. Dashed, not solid — a plan is not approved leave. */
function PlanBar({ plan }: { plan: LeavePlan }) {
  return (
    <div
      className="truncate rounded-sm border border-dashed px-1 py-0.5 text-[11px] leading-tight"
      style={{
        borderColor: typeHue(plan.leave_type_id),
        color: typeHue(plan.leave_type_id),
      }}
      title={`${plan.employee_name} · ${plan.leave_type_name} · ${PLAN_STATUS_META[plan.status].label}`}
    >
      {plan.employee_name}
    </div>
  );
}

/**
 * The Team Plans month grid (spec 3.6).
 *
 * Deliberately drawn with dashed, outlined bars rather than the solid fills the
 * approved/pending leave calendar uses, so a reader never confuses "someone is
 * planning to" with "someone is definitely away". Clicking a day opens the
 * read-only detail overlay; there is no way to act on another person's plan.
 */
export function TeamPlansCalendar() {
  const {
    scopes,
    scope,
    setScope,
    scopesLoaded,
    month,
    shiftMonth,
    data,
    isLoading,
    error,
    refetch,
  } = useTeamPlans();

  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const monthDate = parseISO(`${month}-01`);
  const first = startOfMonth(monthDate);
  const last = endOfMonth(monthDate);
  const gridStart = startOfWeek(first, { weekStartsOn: 1 });

  const days: Date[] = [];
  for (let day = gridStart; day <= last; day = addDays(day, 1)) {
    days.push(day);
    if (days.length > 42) break; // six weeks is the widest any month needs
  }

  const plans = data?.results ?? [];
  const selectedPlans = selectedDay
    ? plansOnDay(plans, parseISO(selectedDay))
    : [];

  if (error && !data) {
    return (
      <ErrorState
        title="Couldn't load the calendar"
        message={error}
        onRetry={refetch}
        retryLabel="Retry"
      />
    );
  }

  if (scopesLoaded && scopes.length === 0) {
    return (
      <EmptyState
        icon={<Calendar className="h-8 w-8 text-text-muted" />}
        title="No team to show yet"
        description="You're not part of a team yet, so there are no plans to show. Once HR places you in a team, your colleagues' plans will appear here."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <ScopeSelector scopes={scopes} value={scope} onChange={setScope} />
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label="Previous month"
            onClick={() => shiftMonth(-1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-36 text-center text-sm font-semibold text-text-primary">
            {format(monthDate, "MMMM yyyy")}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label="Next month"
            onClick={() => shiftMonth(1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading ? (
        <SkeletonRegion label="Loading the team calendar" className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </SkeletonRegion>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border-default bg-surface-card">
          <div className="grid grid-cols-7 border-b border-border-default bg-surface-muted">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <div
                key={d}
                className="px-2 py-2 text-center text-xs font-semibold text-text-muted"
              >
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7">
            {days.map((day) => {
              const iso = format(day, "yyyy-MM-dd");
              const inMonth = day >= first && day <= last;
              const dayPlans = plansOnDay(plans, day);
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => setSelectedDay(iso)}
                  aria-label={format(day, "d MMMM yyyy")}
                  className={cn(
                    "min-h-24 border-b border-r border-border-default p-1 text-left",
                    "focus-ring transition-colors hover:bg-surface-hover",
                    !inMonth && "bg-surface-muted/40 opacity-40",
                  )}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className={cn(
                        "text-xs font-medium text-text-secondary",
                        inMonth && "text-text-primary",
                      )}
                    >
                      {format(day, "d")}
                    </span>
                    {dayPlans.length > 0 && (
                      <Calendar className="h-3 w-3 text-text-muted" aria-hidden="true" />
                    )}
                  </div>
                  <div className="space-y-0.5">
                    {dayPlans.slice(0, 3).map((plan) => (
                      <PlanBar key={plan.id} plan={plan} />
                    ))}
                    {dayPlans.length > 3 && (
                      <div className="text-[10px] text-text-muted">
                        +{dayPlans.length - 3} more
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!isLoading && plans.length === 0 && (
        <EmptyState
          icon={<Calendar className="h-8 w-8 text-text-muted" />}
          title="No planned leave this month"
          description="Nobody in your scope has planned leave in this month."
        />
      )}

      <PlanDetailOverlay
        date={selectedDay}
        plans={selectedPlans}
        onClose={() => setSelectedDay(null)}
      />
    </div>
  );
}
