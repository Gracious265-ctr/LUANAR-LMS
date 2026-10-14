import { formatDate, formatDateTime } from "@/lib/tracking/format";

/** Africa/Blantyre date helpers (shared with the approvals desk). */
export { formatDate, formatDateTime };

/**
 * "12 – 16 Oct 2026", collapsing the repeated year.
 *
 * A plan period usually spans months and a block usually spans days, so
 * printing the year twice wastes the width a table column does not have — but
 * only when the two dates agree on it. A period that crosses a year boundary
 * keeps the opening year, since "28 Dec – 8 Jan" is ambiguous on its own.
 */
export function formatPeriod(
  fromIso: string | null | undefined,
  toIso: string | null | undefined
): string {
  const from = formatDate(fromIso);
  const to = formatDate(toIso);
  const sameYear =
    from !== "" && to !== "" && /\d{4}$/.exec(from)?.[0] === /\d{4}$/.exec(to)?.[0];
  const start = sameYear ? from.replace(/ \d{4}$/, "") : from;
  if (start && to) {
    return `${start} – ${to}`;
  }
  if (start) return `${start} – …`;
  if (to) return `… – ${to}`;
  return "—";
}

/** "3 working days" / "1 working day", or an em dash when not yet computed. */
export function formatWorkingDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return "—";
  return `${days} working ${days === 1 ? "day" : "days"}`;
}
