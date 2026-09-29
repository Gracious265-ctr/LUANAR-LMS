import { formatDate, formatDateTime } from "@/lib/tracking/format";

/** Africa/Blantyre date helpers (shared with Unit 15 tracking). */
export { formatDate, formatDateTime };

export function formatWorkingDays(days: number | null | undefined): string {
  if (days == null) return "—";
  return `${days} ${days === 1 ? "day" : "days"}`;
}