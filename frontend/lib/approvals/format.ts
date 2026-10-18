import { formatDate, formatDateTime } from "@/lib/format";

/** Africa/Blantyre date helpers (shared with Unit 15 tracking). */
export { formatDate, formatDateTime };

export function formatSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}