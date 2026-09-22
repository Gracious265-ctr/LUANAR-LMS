const APP_TIME_ZONE = "Africa/Blantyre";

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: APP_TIME_ZONE,
  hour12: false,
});

const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeZone: "UTC",
});

/**
 * Format an ISO 8601 UTC instant as a Blantyre date + time, e.g.
 * ``2026-10-14T07:15:03Z`` -> "14 Oct 2026, 09:15".
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return DATE_TIME_FORMATTER.format(new Date(value));
}

/**
 * Format a calendar date (start_date/end_date) without time-zone shifting,
 * e.g. "2026-11-02" -> "2 Nov 2026".
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return "";
  return DATE_FORMATTER.format(new Date(Date.UTC(year, month - 1, day)));
}