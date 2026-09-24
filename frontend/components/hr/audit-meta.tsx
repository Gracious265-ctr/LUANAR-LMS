import { ACTION_LABELS } from "@/lib/audit";
import type { AuditEntry } from "@/lib/audit";

export function auditActionTone(action: string): string {
  if (action.endsWith(".approved")) {
    return "bg-brand-secondary-subtle text-brand-secondary";
  }
  if (action.endsWith(".rejected") || action.endsWith(".cancelled")) {
    return "bg-status-rejected-subtle text-status-rejected";
  }
  if (
    action.endsWith(".submitted") ||
    action.endsWith(".reassigned") ||
    action.endsWith(".resubmitted")
  ) {
    return "bg-brand-primary-subtle text-brand-primary";
  }
  return "bg-surface-muted text-text-muted";
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
    case "workflow":
      return `/dashboard/hr-admin/workflows/${entry.target_id}/edit`;
    case "leavetype":
      return `/dashboard/hr-admin/leave-types/${entry.target_id}/edit`;
    case "leaverule":
      return `/dashboard/hr-admin/leave-rules/${entry.target_id}/edit`;
    case "gradeentitlement":
      return `/dashboard/hr-admin/entitlements/${entry.target_id}/edit`;
    case "financialyear":
      return `/dashboard/hr-admin/calendar/financial-years/${entry.target_id}/edit`;
    case "publicholiday":
      return `/dashboard/hr-admin/calendar/holidays/${entry.target_id}/edit`;
    case "employeeprofile":
      return `/dashboard/hr-admin/employees/${entry.target_id}`;
    case "leavedocumenttemplate":
      return "/dashboard/hr-admin/leave-document-template";
    case "leaveapplication":
      return `/dashboard/hr-admin/audit/applications/${entry.target_id}`;
    default:
      return null;
  }
}

/** A short, human-readable summary of an entry's changed fields (or reason). */
export function auditChangesText(entry: AuditEntry): string {
  const reason = entry.reason || entry.new_state || "";
  if (!entry.detail) {
    return reason || "\u2014";
  }
  const after = entry.detail.after;
  const changes = Object.keys(after);
  if (changes.length === 0) {
    return reason || "\u2014";
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
  if (reason) {
    parts.push(`Reason: ${reason}`);
  }
  if (parts.length <= 2) {
    return parts.join(", ");
  }
  return parts.slice(0, 2).join(", ") + ` (+${parts.length - 2} more)`;
}