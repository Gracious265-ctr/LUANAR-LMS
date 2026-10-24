/**
 * Client-safe working-day vocabulary.
 *
 * Split out of `financial-years.ts`, which reads Django through `api-client`
 * and therefore drags `next/headers` into any client bundle that value-imports
 * it. These constants and types have no server dependency, so a client
 * component (the working-days form) can use them without that cost.
 */
export const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

export type Weekday = (typeof WEEKDAYS)[number];

export type WorkingDayPattern = Record<Weekday, boolean>;

export const WEEKDAY_LABELS: Record<Weekday, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};
