"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { detectConflicts, eachDay } from "@/lib/calendar/conflicts";
import { leaveTypeTone } from "@/lib/calendar/leave-type-colors";
import { fetchTeamCalendar } from "@/lib/calendar/service";
import type {
  CalendarEmployeeRef,
  CalendarEntry,
  TeamCalendarResponse,
} from "@/lib/calendar/types";
import { cn } from "@/lib/utils";

const DAY_WIDTH = 28;
const NAME_WIDTH = 168;
const ROW_HEIGHT = 36;

export interface TeamLeaveCalendarProps {
  unitId: number;
  /**
   * The id of the application under review. Its bar is ring-highlighted so the
   * approver can see the request in context: "here is the gap this would fill".
   */
  highlightEntryId?: string | null;
  /** Latest loaded payload (or null while unavailable), for a sibling warning. */
  onData?: (data: TeamCalendarResponse | null) => void;
  initialMonth?: string;
  className?: string;
}

interface MemberRow {
  employee: CalendarEmployeeRef;
  entries: CalendarEntry[];
}

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [year, monthNumber] = month.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, monthNumber - 1 + delta, 1));
  return `${shifted.getUTCFullYear()}-${String(
    shifted.getUTCMonth() + 1
  ).padStart(2, "0")}`;
}

function monthBounds(month: string): { start: string; end: string } {
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  return {
    start: `${month}-01`,
    end: `${month}-${String(lastDay).padStart(2, "0")}`,
  };
}

function monthTitle(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number);
  return new Date(Date.UTC(year, monthNumber - 1, 1)).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function groupMembers(entries: CalendarEntry[]): MemberRow[] {
  const rows = new Map<number, MemberRow>();
  for (const entry of entries) {
    const existing = rows.get(entry.employee.id);
    if (existing) {
      existing.entries.push(entry);
    } else {
      rows.set(entry.employee.id, {
        employee: entry.employee,
        entries: [entry],
      });
    }
  }
  return [...rows.values()];
}

/**
 * The team leave calendar (spec 3.1): a Gantt-style month grid, one row per
 * team member, approved leave as solid bars and pending as hatched ones.
 * Over-subscribed days are striped with the warning token rather than
 * recolouring the bars themselves (spec 3.2), so the two readings stay
 * separable at a glance.
 */
export function TeamLeaveCalendar({
  unitId,
  highlightEntryId,
  onData,
  initialMonth,
  className,
}: TeamLeaveCalendarProps) {
  const [month, setMonth] = useState(initialMonth ?? currentMonth());
  const [data, setData] = useState<TeamCalendarResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error" | "not_found">(
    "loading"
  );
  const [message, setMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // Keep the callback out of the fetch effect's dependencies: a parent that
  // passes an inline function would otherwise re-fetch on every render.
  const onDataRef = useRef(onData);
  useEffect(() => {
    onDataRef.current = onData;
  }, [onData]);

  useEffect(() => {
    let cancelled = false;
    fetchTeamCalendar(unitId, month).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setData(result.data);
        setState("ready");
        setMessage("");
        onDataRef.current?.(result.data);
      } else {
        setData(null);
        setState(result.kind);
        setMessage(result.message);
        onDataRef.current?.(null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [unitId, month, reloadKey]);

  // The loading reset happens in the handlers (like the review page's retry),
  // never synchronously in the effect, so changing month does not cascade a
  // render before the fetch even starts.
  function changeMonth(delta: number) {
    setState("loading");
    setData(null);
    onDataRef.current?.(null);
    setMonth((value) => shiftMonth(value, delta));
  }

  function retry() {
    setState("loading");
    setReloadKey((value) => value + 1);
  }

  const bounds = monthBounds(month);
  const days = eachDay(bounds.start, bounds.end);
  const members = data ? groupMembers(data.entries) : [];
  const conflicts = data
    ? detectConflicts(data.entries, data.conflict_threshold, bounds)
    : [];
  const conflictDays = new Set(
    conflicts.flatMap((range) => eachDay(range.start, range.end))
  );

  return (
    <section
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle",
        className
      )}
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
          <CalendarDays className="h-4 w-4 text-text-muted" aria-hidden="true" />
          Team calendar
        </h2>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Previous month"
            onClick={() => changeMonth(-1)}
            className="grid h-8 w-8 place-content-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover focus-ring"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <span className="min-w-32 text-center text-sm font-medium text-text-primary">
            {monthTitle(month)}
          </span>
          <button
            type="button"
            aria-label="Next month"
            onClick={() => changeMonth(1)}
            className="grid h-8 w-8 place-content-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover focus-ring"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {state === "loading" && (
        <div className="space-y-2" aria-hidden="true">
          <div className="h-4 w-40 animate-pulse rounded bg-surface-muted" />
          <div className="h-24 animate-pulse rounded-lg bg-surface-muted" />
        </div>
      )}

      {state === "not_found" && (
        <p className="text-sm text-text-secondary">{message}</p>
      )}

      {state === "error" && (
        <div className="space-y-3">
          <p className="text-sm text-status-rejected">{message}</p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={retry}
          >
            Retry
          </Button>
        </div>
      )}

      {state === "ready" &&
        (members.length === 0 ? (
          <EmptyState
            titleAs="h3"
            title="No leave scheduled this month."
            description={
              data?.unit_name
                ? `Nobody on ${data.unit_name} has approved or pending leave in ${monthTitle(month)}.`
                : undefined
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <div style={{ minWidth: NAME_WIDTH + days.length * DAY_WIDTH }}>
                <div className="flex">
                  <div
                    className="shrink-0 pr-2 text-xs font-medium text-text-muted"
                    style={{ width: NAME_WIDTH }}
                  >
                    Team member
                  </div>
                  {days.map((day) => {
                    const date = Number(day.slice(-2));
                    const weekday = new Date(`${day}T00:00:00Z`).getUTCDay();
                    const weekend = weekday === 0 || weekday === 6;
                    return (
                      <div
                        key={day}
                        style={{ width: DAY_WIDTH }}
                        className={cn(
                          "shrink-0 text-center text-[10px] tabular-nums",
                          weekend ? "text-text-muted" : "text-text-secondary"
                        )}
                      >
                        {date}
                      </div>
                    );
                  })}
                </div>

                <div
                  className="relative mt-1"
                  style={{ height: members.length * ROW_HEIGHT }}
                >
                  {conflicts.flatMap((range) =>
                    eachDay(range.start, range.end).map((day) => {
                      const index = days.indexOf(day);
                      if (index < 0) return null;
                      return (
                        <span
                          key={`conflict-${day}`}
                          data-conflict-day={day}
                          aria-hidden="true"
                          className="absolute inset-y-0 border-x border-border-warning bg-amber-100/70"
                          style={{
                            left: NAME_WIDTH + index * DAY_WIDTH,
                            width: DAY_WIDTH,
                          }}
                        />
                      );
                    })
                  )}

                  {members.map((member, row) => (
                    <div
                      key={member.employee.id}
                      data-testid={`calendar-row-${member.employee.id}`}
                      className="absolute inset-x-0 flex items-center"
                      style={{ top: row * ROW_HEIGHT, height: ROW_HEIGHT }}
                    >
                      <div
                        className="flex min-w-0 shrink-0 items-center gap-2 pr-2"
                        style={{ width: NAME_WIDTH }}
                      >
                        <Avatar
                          name={member.employee.name}
                          userId={member.employee.id}
                          size="sm"
                        />
                        <span className="truncate text-xs font-medium text-text-primary">
                          {member.employee.name}
                        </span>
                      </div>
                      <div
                        className="relative shrink-0"
                        style={{
                          width: days.length * DAY_WIDTH,
                          height: ROW_HEIGHT,
                        }}
                      >
                        {days.map((day, index) => (
                          <span
                            key={day}
                            aria-hidden="true"
                            className={cn(
                              "absolute inset-y-0 border-r border-border-default",
                              conflictDays.has(day) && "border-transparent"
                            )}
                            style={{
                              left: index * DAY_WIDTH,
                              width: DAY_WIDTH,
                            }}
                          />
                        ))}
                        {member.entries.map((entry) => {
                          const startIndex = Math.max(
                            0,
                            days.indexOf(
                              entry.start_date > bounds.start
                                ? entry.start_date
                                : bounds.start
                            )
                          );
                          const endDate =
                            entry.end_date < bounds.end
                              ? entry.end_date
                              : bounds.end;
                          const endIndex = days.indexOf(endDate);
                          if (endIndex < 0) return null;
                          const tone = leaveTypeTone(entry.leave_type);
                          const pending = entry.status === "pending";
                          const highlighted =
                            highlightEntryId != null &&
                            entry.id === highlightEntryId;
                          return (
                            <span
                              key={entry.id}
                              data-testid={`calendar-bar-${entry.id}`}
                              data-status={entry.status}
                              title={`${member.employee.name} · ${entry.leave_type.name} · ${entry.status}`}
                              className={cn(
                                "absolute top-1.5 flex h-6 items-center overflow-hidden rounded px-1.5 text-[10px] font-medium text-slate-800",
                                pending && "border-dashed",
                                highlighted &&
                                  "ring-2 ring-brand-primary ring-offset-1"
                              )}
                              style={{
                                left: startIndex * DAY_WIDTH + 2,
                                width:
                                  (endIndex - startIndex + 1) * DAY_WIDTH - 4,
                                backgroundColor: tone.fill,
                                borderColor: tone.border,
                                borderStyle: pending ? "dashed" : "solid",
                                borderWidth: 1,
                                backgroundImage: pending
                                  ? "repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.75) 3px, rgba(255,255,255,0.75) 6px)"
                                  : undefined,
                              }}
                            >
                              <span className="truncate">
                                {entry.leave_type.name}
                              </span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-3 w-6 rounded border border-solid border-border-strong bg-surface-muted"
                />
                Approved
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-3 w-6 rounded border border-dashed border-border-strong"
                  style={{
                    backgroundImage:
                      "repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.75) 3px, rgba(255,255,255,0.75) 6px)",
                  }}
                />
                Pending
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-3 w-6 rounded border border-border-warning bg-amber-100/70"
                />
                Conflict day
              </span>
            </div>
          </>
        ))}
    </section>
  );
}
