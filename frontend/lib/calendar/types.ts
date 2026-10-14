/** Team leave calendar payload (UI/UX Phase 2, spec 3.1). */

export type CalendarEntryStatus = "pending" | "approved";

export interface CalendarEmployeeRef {
  id: number;
  name: string;
}

export interface CalendarLeaveTypeRef {
  id: number | null;
  code: string | null;
  name: string;
}

export interface CalendarEntry {
  id: string;
  employee: CalendarEmployeeRef;
  /** ISO date, "YYYY-MM-DD". */
  start_date: string;
  /** ISO date, "YYYY-MM-DD". */
  end_date: string;
  leave_type: CalendarLeaveTypeRef;
  status: CalendarEntryStatus;
}

export interface TeamCalendarResponse {
  unit_id: number;
  unit_name: string;
  /** "YYYY-MM". */
  month: string;
  team_size: number;
  /** The most people who may be out at once without a conflict. */
  conflict_threshold: number;
  entries: CalendarEntry[];
}

/** A run of consecutive days the team is over-subscribed on. */
export interface ConflictRange {
  /** ISO date of the first day in the run. */
  start: string;
  /** ISO date of the last day in the run. */
  end: string;
  /** The highest simultaneous headcount anywhere in the run. */
  count: number;
}

export interface ConflictDay {
  /** ISO date. */
  day: string;
  count: number;
}
