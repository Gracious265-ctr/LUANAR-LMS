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

/** Edit-page route for a target the HR UI can change, or null when read-only. */
export function auditEditHref(entry: AuditEntry): string | null {
  switch (entry.target_type) {
    case "team":
      return `/dashboard/hr-admin/teams/${entry.target_id}`;
    case "leavetype":
      return `/dashboard/hr-admin/leave-types/${entry.target_id}/edit`;
    case "leaverule":
      return `/dashboard/hr-admin/leave-rules/${entry.target_id}/edit`;
    case "entitlement":
      return `/dashboard/hr-admin/entitlements/${entry.target_id}/edit`;
    case "financialyear":
      return `/dashboard/hr-admin/calendar/financial-years/${entry.target_id}/edit`;
    case "publicholiday":
      return `/dashboard/hr-admin/calendar/holidays/${entry.target_id}/edit`;
    case "employee":
      return `/dashboard/hr-admin/employees/${entry.target_id}`;
    case "document-template":
      return "/dashboard/hr-admin/leave-document-template";
    default:
      return null;
  }
}

const MAX_PAIRS = 2;
/** Keeps one fat value (a JSON blob in a flat payload) from wrecking the cell. */
const MAX_VALUE_CHARS = 80;

function truncate(value: string): string {
  return value.length > MAX_VALUE_CHARS
    ? `${value.slice(0, MAX_VALUE_CHARS - 1)}\u2026`
    : value;
}

function joinPairs(parts: string[]): string {
  if (parts.length <= MAX_PAIRS) {
    return parts.join(", ");
  }
  return `${parts.slice(0, MAX_PAIRS).join(", ")} (+${parts.length - MAX_PAIRS} more)`;
}

/** A `{"before": ..., "after": ...}` diff, or null when `detail` is not one. */
function asDiff(
  detail: Record<string, unknown>
): { before: Record<string, unknown>; after: Record<string, unknown> } | null {
  const { before, after } = detail;
  if (after === null || typeof after !== "object" || Array.isArray(after)) {
    return null;
  }
  return {
    before:
      before !== null && typeof before === "object" && !Array.isArray(before)
        ? (before as Record<string, unknown>)
        : {},
    after: after as Record<string, unknown>,
  };
}

/** A short, human-readable summary of an entry's changed fields (or reason). */
export function auditChangesText(entry: AuditEntry): string {
  const detail = entry.detail;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) {
    return entry.reason || "\u2014";
  }

  const diff = asDiff(detail);
  if (diff) {
    const changes = Object.keys(diff.after);
    if (changes.length === 0) {
      return entry.reason || "\u2014";
    }
    const parts = changes.map((field) => {
      const oldValue = diff.before[field];
      const newValue = diff.after[field];
      const display =
        oldValue !== undefined
          ? `${formatAuditValue(oldValue)} \u2192 ${formatAuditValue(newValue)}`
          : formatAuditValue(newValue);
      return `${field}: ${display}`;
    });
    if (entry.reason) {
      parts.push(`Reason: ${entry.reason}`);
    }
    return joinPairs(parts);
  }

  // Flat payload shape. `detail` is a free-form JSON bag, not always a diff:
  // `document_generated` records the file, `stage_skipped` the bypassed stages.
  // Reading those as a diff threw on `Object.keys(undefined)` and took the
  // whole audit page down, so they are summarised instead.
  const parts = Object.entries(detail).map(
    ([key, value]) => `${key}: ${truncate(formatAuditValue(value))}`
  );
  if (parts.length === 0) {
    return entry.reason || "\u2014";
  }
  // Only add the entry-level reason when the payload has none of its own, so
  // `stage_skipped` does not print its reason twice.
  if (entry.reason && !("reason" in detail)) {
    parts.push(`Reason: ${truncate(entry.reason)}`);
  }
  return joinPairs(parts);
}
