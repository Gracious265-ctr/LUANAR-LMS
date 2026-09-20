import { ACTION_LABELS } from "@/lib/audit";
import type { AuditEntry } from "@/lib/audit";

export function auditActionTone(action: string): string {
  switch (action) {
    case "approved":
      return "bg-brand-secondary-subtle text-brand-secondary";
    case "rejected":
    case "cancelled":
      return "bg-status-rejected-subtle text-status-rejected";
    case "submitted":
    case "reassigned":
      return "bg-brand-primary-subtle text-brand-primary";
    default:
      return "bg-surface-muted text-text-muted";
  }
}

export function AuditActionPill({ action }: { action: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${auditActionTone(action)}`}
    >
      {ACTION_LABELS[action] || action}
    </span>
  );
}

export function formatAuditValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length > 0
      ? value
          .map((item) =>
            typeof item === "string" ? item : JSON.stringify(item)
          )
          .join(", ")
      : "none";
  }
  if (value === null || value === undefined) {
    return "none";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

/** A short, human-readable summary of an entry's changed fields (or reason). */
export function auditChangesText(entry: AuditEntry): string {
  if (!entry.detail) {
    return entry.reason || "\u2014";
  }
  const after = entry.detail.after;
  const changes = Object.keys(after);
  if (changes.length === 0) {
    return entry.reason || "\u2014";
  }
  const before = entry.detail.before ?? {};
  const parts = changes.map((field) => {
    const oldValue = before[field];
    const newValue = after[field];
    const display =
      oldValue !== undefined
        ? `${formatAuditValue(oldValue)} \u2192 ${formatAuditValue(newValue)}`
        : formatAuditValue(newValue);
    return `${field}: ${display}`;
  });
  if (entry.reason) {
    parts.push(`Reason: ${entry.reason}`);
  }
  if (parts.length <= 2) {
    return parts.join(", ");
  }
  return parts.slice(0, 2).join(", ") + ` (+${parts.length - 2} more)`;
}