import { formatDate, formatDateTime } from "@/lib/tracking/format";

<<<<<<< HEAD
import type { DecisionAction, LeaveHistoryItem } from "./types";

export const DECISION_LABELS: Record<DecisionAction, string> = {
  approve: "Approve",
  reject: "Reject",
  return_for_correction: "Return for Correction",
};

export const DECISION_PAST_TENSE: Record<DecisionAction, string> = {
  approve: "approved",
  reject: "rejected",
  return_for_correction: "returned for correction",
};

export function decisionLabel(action: DecisionAction): string {
  return DECISION_LABELS[action];
}

export function decisionPastTense(action: DecisionAction): string {
  return DECISION_PAST_TENSE[action];
}

export function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined
): string {
  const startLabel = formatDate(start);
  const endLabel = formatDate(end);
  if (!startLabel && !endLabel) return "";
  if (!endLabel) return startLabel;
  if (!startLabel) return endLabel;
  return `${startLabel} – ${endLabel}`;
}

export function formatBytes(value: number | null | undefined): string {
  if (!value || value <= 0) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function leaveHistoryNote(history: {
  available: boolean;
  scope: string | null;
  items: LeaveHistoryItem[];
}): string {
  if (!history.available) {
    return "Leave history is not available for your role.";
  }
  if (history.scope === "current_financial_year") {
    return "Showing leave within the current financial year.";
  }
  return "Showing the employee's recent leave history.";
}

export { formatDate, formatDateTime };
=======
/** Africa/Blantyre date helpers (shared with Unit 15 tracking). */
export { formatDate, formatDateTime };

export function formatSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
>>>>>>> feature/plans-teams
