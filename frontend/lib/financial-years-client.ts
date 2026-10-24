import { apiErrorMessage } from "./utils";
import type {
  CalendarEvent,
  CalendarEventInput,
  FinancialYear,
  FinancialYearInput,
  Holiday,
  HolidayInput,
  WorkingDayPattern,
} from "./financial-years";

export async function createFinancialYear(
  input: FinancialYearInput
): Promise<FinancialYear> {
  return proxyWrite<FinancialYear>("/api/hr/financial-years", "POST", input);
}

export async function updateFinancialYear(
  id: number | string,
  input: FinancialYearInput
): Promise<FinancialYear> {
  return proxyWrite<FinancialYear>(
    `/api/hr/financial-years/${id}`,
    "PATCH",
    input
  );
}

/**
 * Delete a financial year.
 *
 * The backend refuses with 409 while a leave entitlement or plan still
 * references the period and answers with a sentence saying so; that refusal is
 * surfaced to HR rather than hidden, because the blocker is theirs to clear.
 */
export async function deleteFinancialYear(id: number | string): Promise<void> {
  await proxyWrite<void>(`/api/hr/financial-years/${id}`, "DELETE");
}

export async function createHoliday(input: HolidayInput): Promise<Holiday> {
  return proxyWrite<Holiday>("/api/hr/holidays", "POST", input);
}

export async function updateHoliday(
  id: number | string,
  input: HolidayInput
): Promise<Holiday> {
  return proxyWrite<Holiday>(`/api/hr/holidays/${id}`, "PATCH", input);
}

export async function deleteHoliday(id: number | string): Promise<void> {
  await proxyWrite<void>(`/api/hr/holidays/${id}`, "DELETE");
}

export async function createCalendarEvent(
  input: CalendarEventInput
): Promise<CalendarEvent> {
  return proxyWrite<CalendarEvent>("/api/hr/calendar-events", "POST", input);
}

export async function updateCalendarEvent(
  id: number | string,
  input: CalendarEventInput
): Promise<CalendarEvent> {
  return proxyWrite<CalendarEvent>(
    `/api/hr/calendar-events/${id}`,
    "PATCH",
    input
  );
}

export async function deleteCalendarEvent(id: number | string): Promise<void> {
  await proxyWrite<void>(`/api/hr/calendar-events/${id}`, "DELETE");
}

export async function updateWorkingDayPattern(
  input: WorkingDayPattern
): Promise<WorkingDayPattern> {
  return proxyWrite<WorkingDayPattern>(
    "/api/hr/working-days",
    "PATCH",
    input
  );
}

async function proxyWrite<T>(
  endpoint: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) {
    return undefined as T;
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}
