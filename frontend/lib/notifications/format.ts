import { format, formatDistanceToNow } from "date-fns";

/**
 * Relative label plus the absolute string for hover — the same pairing the
 * leave lists use: glanceable by default ("2 hours ago"), exact on demand via
 * the `<time>` element's `title`.
 */
export function relativeTime(iso: string): { label: string; absolute: string } {
  const date = new Date(iso);
  return {
    label: formatDistanceToNow(date, { addSuffix: true }),
    absolute: format(date, "PPPP p"),
  };
}
