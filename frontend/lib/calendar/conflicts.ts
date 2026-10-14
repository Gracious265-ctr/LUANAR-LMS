import type { CalendarEntry, ConflictDay, ConflictRange } from "./types";

/**
 * Conflict detection for the team calendar (spec 3.2).
 *
 * The rule is one pure function so the stripe the approver sees and the inline
 * warning beside Approve are the same arithmetic the server uses before it
 * refuses the decision (`backend/leave/conflicts.py`). A day is "in conflict"
 * when more than `threshold` people are simultaneously away.
 */

function toIso(day: Date): string {
  return day.toISOString().slice(0, 10);
}

function parse(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

/** Every ISO date from `start` to `end`, inclusive. */
export function eachDay(start: string, end: string): string[] {
  const days: string[] = [];
  if (!start || !end || start > end) return days;
  const cursor = parse(start);
  const last = parse(end);
  while (cursor.getTime() <= last.getTime()) {
    days.push(toIso(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

/** How many entries cover `day`. */
export function countOnDay(entries: CalendarEntry[], day: string): number {
  return entries.filter(
    (entry) => entry.start_date <= day && day <= entry.end_date
  ).length;
}

/**
 * Days the team is over the cap on, as runs of consecutive days.
 *
 * `bound` limits the window that is walked. It matters because an entry may
 * start before (or end after) the month being drawn: without a bound the
 * stripes for one month could be computed from days the grid never shows.
 */
export function detectConflicts(
  entries: CalendarEntry[],
  threshold: number,
  bound?: { start: string; end: string }
): ConflictRange[] {
  if (entries.length === 0) return [];

  let start = bound?.start;
  let end = bound?.end;
  if (!start || !end) {
    const starts = entries.map((entry) => entry.start_date).sort();
    const ends = entries.map((entry) => entry.end_date).sort();
    start = start ?? starts[0];
    end = end ?? ends[ends.length - 1];
  }

  const ranges: ConflictRange[] = [];
  let current: ConflictRange | null = null;

  for (const day of eachDay(start, end)) {
    const count = countOnDay(entries, day);
    if (count > threshold) {
      if (current) {
        current.end = day;
        current.count = Math.max(current.count, count);
      } else {
        current = { start: day, end: day, count };
      }
    } else if (current) {
      ranges.push(current);
      current = null;
    }
  }
  if (current) ranges.push(current);
  return ranges;
}

/**
 * The first day in `[start, end]` where approving the request would push the
 * team over the cap, with that day's headcount — the number the inline warning
 * and the server's 409 both name.
 */
export function firstConflict(
  entries: CalendarEntry[],
  threshold: number,
  start: string,
  end: string
): ConflictDay | null {
  for (const day of eachDay(start, end)) {
    const count = countOnDay(entries, day);
    if (count > threshold) return { day, count };
  }
  return null;
}
