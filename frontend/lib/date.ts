import { format, isAfter, isBefore, isValid, parseISO } from "date-fns";

export const ISO_DATE_PATTERN = "yyyy-MM-dd";
export const DISPLAY_DATE_PATTERN = "dd MMM yyyy";

/** Formats a `Date` the calendar produced into the `yyyy-MM-dd` string the API expects. */
export function toIsoDate(date: Date): string {
  return format(date, ISO_DATE_PATTERN);
}

/** Parses a `yyyy-MM-dd` string into the local-midnight `Date` the calendar renders. */
export function fromIsoDate(
  iso: string | null | undefined
): Date | undefined {
  if (!iso) return undefined;
  const parsed = parseISO(iso);
  return isValid(parsed) ? parsed : undefined;
}

export function formatDisplayDate(iso: string | null | undefined): string {
  const date = fromIsoDate(iso);
  return date ? format(date, DISPLAY_DATE_PATTERN) : "";
}

export function formatDateRange(
  fromIso: string | null | undefined,
  toIso: string | null | undefined
): string {
  const from = formatDisplayDate(fromIso);
  const to = formatDisplayDate(toIso);
  if (from && to) return `${from} – ${to}`;
  if (from) return `${from} – …`;
  return "";
}

/** Inclusive `min`/`max` guard for calendar days; both bounds are optional. */
export function isDateOutsideBounds(
  day: Date,
  min?: string,
  max?: string
): boolean {
  const minDate = fromIsoDate(min);
  const maxDate = fromIsoDate(max);
  if (minDate && isBefore(day, minDate)) return true;
  if (maxDate && isAfter(day, maxDate)) return true;
  return false;
}

/** How many years either side of the current year the calendars can page to. */
const NAV_YEARS = 5;

/**
 * The month range the calendars may navigate.
 *
 * `react-day-picker` pages within the current calendar year by default, so a
 * plan period or financial year running past December — which the native
 * `<input type="date">` these pickers replaced could always reach — would be
 * unreachable. Callers with tighter needs should pass explicit `min`/`max`
 * bounds instead; this only widens navigation, not day selection.
 */
export function dateNavBounds(today: Date = new Date()): {
  startMonth: Date;
  endMonth: Date;
} {
  return {
    startMonth: new Date(today.getFullYear() - NAV_YEARS, 0, 1),
    endMonth: new Date(today.getFullYear() + NAV_YEARS, 11, 31),
  };
}
