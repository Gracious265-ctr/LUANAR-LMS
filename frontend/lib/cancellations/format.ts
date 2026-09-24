import { formatDate, formatDateTime } from "@/lib/tracking/format";
import { formatDayCount } from "./labels";

/** Africa/Blantyre date helpers (shared with Unit 15 tracking). */
export { formatDate, formatDateTime };

export function formatRestorationDays(days: string): string {
  return `${formatDayCount(days)} day${Number(days) === 1 ? "" : "s"}`;
}