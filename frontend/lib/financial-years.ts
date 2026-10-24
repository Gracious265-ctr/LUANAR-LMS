import { redirect } from "next/navigation";

import { apiClient, type DjangoUser } from "./api-client";
import { getCurrentUser } from "./auth";
import { currentDateIso } from "./utils";
import type { WorkingDayPattern } from "./calendar-weekdays";

/**
 * Server-side reader for the Calendar app (§3.7).
 *
 * Financial years are the shared `leave.FinancialYear` rows, now exposed under
 * the calendar app's own `/api/v1/calendar/` paths. Holidays are the calendar
 * app's `Holiday` rows, which replaced `leave.PublicHoliday`; everything read
 * here is open to any authenticated user while writes are HR-only.
 */
const CALENDAR = "/api/v1/calendar";

/**
 * Mirror of `calendar_app.services.can_access_calendar` (§2).
 *
 * The launcher's card and the Django gate admit superusers as well as HR — the
 * serialized user carries `is_superuser` and `role`, so those are the two arms
 * this can see. `is_staff`, the backend's third arm, is not serialized, exactly
 * as it is missing from the shell's other mirrors; a `createsuperuser` account
 * sets `is_superuser` too, so it is covered here.
 */
export function canAccessCalendar(user: DjangoUser | null): boolean {
  if (!user) return false;
  if (user.is_superuser === true) return true;
  return user.role === "hr";
}

/**
 * The gate every Calendar page calls first: no user to the login page, and
 * anyone the launcher would not show the card to back to their dashboard.
 * Without the superuser arm a superuser saw the launcher card and was bounced
 * to `/dashboard` the moment they opened it.
 */
export async function requireCalendarAccess(): Promise<DjangoUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }
  if (!canAccessCalendar(user)) {
    redirect("/dashboard");
  }
  return user;
}

export interface FinancialYear {
  id: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface FinancialYearInput {
  start_date: string;
  end_date: string;
  is_active?: boolean;
}

export interface FinancialYearListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FinancialYear[];
}

<<<<<<< HEAD
export interface Holiday {
=======
/** One employee's carry-over outcome from a rejected-leave rollover. */
export interface CarryOverEmployee {
  employee_id: number;
  days: string;
  /** True when this rollover created the row; false when it already existed. */
  created: boolean;
}

/** The result of running (or previewing) a rejected-leave rollover. */
export interface CarryOverResult {
  from_financial_year: string;
  to_financial_year: string;
  dry_run: boolean;
  employees: CarryOverEmployee[];
  total_days: string;
}

export interface PublicHoliday {
>>>>>>> features/team-base
  id: number;
  name: string;
  /** For a recurring holiday this is the reference date, not the occurrence. */
  date: string;
  is_recurring: boolean;
  observed_shift: boolean;
  /** `null` for an institution-wide holiday not scoped to a financial year. */
  financial_year: number | null;
}
<<<<<<< HEAD

export interface HolidayInput {
=======
export interface PublicHolidayInput {
>>>>>>> features/team-base
  name: string;
  date: string;
  is_recurring: boolean;
  observed_shift: boolean;
  financial_year: number | null;
}

export interface HolidayListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Holiday[];
}

/**
 * One resolved occurrence from `?start=&end=`: a recurring holiday unfolded
 * into a concrete date with `observed_shift` already applied. The endpoint
 * returns a bare array rather than a paginated page.
 */
export interface ResolvedHoliday {
  date: string;
  name: string;
  is_recurring: boolean;
  observed_shift: boolean;
  holiday_id: number;
}

export interface CalendarEvent {
  id: number;
  title: string;
  start_date: string;
  end_date: string;
  description: string;
  affects_leave_calculation: boolean;
}

export interface CalendarEventInput {
  title: string;
  start_date: string;
  end_date: string;
  description: string;
  affects_leave_calculation: boolean;
}

export interface CalendarEventListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: CalendarEvent[];
}

/** The seven flags of the single institution-wide working-day pattern (§3.4). */
export {
  WEEKDAYS,
  WEEKDAY_LABELS,
  type Weekday,
  type WorkingDayPattern,
} from "./calendar-weekdays";

export async function listFinancialYears(): Promise<FinancialYearListResponse> {
  return apiClient<FinancialYearListResponse>(`${CALENDAR}/financial-years/`);
}

export async function getFinancialYear(
  id: number | string
): Promise<FinancialYear> {
  return apiClient<FinancialYear>(`${CALENDAR}/financial-years/${id}/`);
}

export async function listHolidays(
  year?: number | string
): Promise<HolidayListResponse> {
  const qs = year ? `?year=${encodeURIComponent(String(year))}` : "";
  return apiClient<HolidayListResponse>(`${CALENDAR}/holidays/${qs}`);
}

export async function getHoliday(id: number | string): Promise<Holiday> {
  return apiClient<Holiday>(`${CALENDAR}/holidays/${id}/`);
}

/** Holidays resolved into concrete dates over a range (recurrence + shift). */
export async function listResolvedHolidays(
  start: string,
  end: string
): Promise<ResolvedHoliday[]> {
  const params = new URLSearchParams({ start, end });
  return apiClient<ResolvedHoliday[]>(`${CALENDAR}/holidays/?${params}`);
}

export async function listCalendarEvents(
  range?: { start?: string; end?: string }
): Promise<CalendarEventListResponse> {
  const params = new URLSearchParams();
  if (range?.start) params.set("start", range.start);
  if (range?.end) params.set("end", range.end);
  const qs = params.toString();
  return apiClient<CalendarEventListResponse>(
    `${CALENDAR}/events/${qs ? `?${qs}` : ""}`
  );
}

export async function getCalendarEvent(
  id: number | string
): Promise<CalendarEvent> {
  return apiClient<CalendarEvent>(`${CALENDAR}/events/${id}/`);
}

export async function getWorkingDayPattern(): Promise<WorkingDayPattern> {
  return apiClient<WorkingDayPattern>(`${CALENDAR}/working-days/`);
}

export function financialYearStatus(
  year: FinancialYear,
  today: string = currentDateIso()
): "active" | "upcoming" | "past" {
  if (year.is_active) {
    return "active";
  }
  if (year.start_date > today) {
    return "upcoming";
  }
  return "past";
}
