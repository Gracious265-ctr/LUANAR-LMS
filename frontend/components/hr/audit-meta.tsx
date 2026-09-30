import { ACTION_LABELS } from "@/lib/audit";
import type { AuditEntry } from "@/lib/audit";
import { Badge, type BadgeTone } from "@/components/ui/badge";

export function auditActionTone(action: string): BadgeTone {
  switch (action) {
    case "approved":
    case "plan_approved":
      return "info";
    case "rejected":
    case "cancelled":
    case "plan_rejected":
      return "rejected";
    case "submitted":
    case "reassigned":
    case "plan_submitted":
    case "plan_confirmed":
    case "plan_released":
      return "brand";
    default:
      return "muted";
  }
}

export function AuditActionPill({ action }: { action: string }) {
  return (
    <Badge
      size="sm"
      tone={auditActionTone(action)}
      className="font-medium whitespace-nowrap"
    >
      {ACTION_LABELS[action] || action}
    </Badge>
  );
}

/** Readable labels for audit-log payload keys (configuration and state fields). */
const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  status: "Status",
  days: "Days",
  duration: "Duration",
  working_days: "Working days",
  decision_version: "Approval round",
  current_stage_order: "Stage",
  reference_number: "Reference",
  financial_year: "Financial year",
  carry_forward_eligible: "Carry-forward eligible",
  start_date: "Start date",
  end_date: "End date",
  period_start: "Period start",
  period_end: "Period end",
  file_name: "File",
  file_size: "Size",
  document_id: "Document ID",
  kind: "Type",
  order: "Stage",
  role: "Role",
  comment: "Comment",
  stage: "Stage",
  stage_version: "Stage version",
  applicant_stage_orders: "Applicant stages",
  skipped_stages: "Skipped stages",
  notification_state: "Notification",
  balance_restored_days: "Days restored",
  request: "Request",
};

/** Readable labels for status-code values recorded in audit payloads. */
const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  pending: "Pending",
  correction_required: "Correction required",
  cancelled: "Cancelled",
  not_required: "Not required",
  reserved: "Reserved",
  confirmed: "Confirmed",
  lapsed: "Lapsed",
  released: "Released",
  waiting: "Waiting",
  skipped: "Skipped",
};

/** Readable labels for reason/code values (e.g. stage_skipped payloads). */
const VALUE_LABELS: Record<string, string> = {
  applicant_is_the_approver: "The applicant is also the approver",
  approved_leave: "Approved leave",
};

function readableValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "none";
  }
  const raw = String(value);
  if (STATUS_LABELS[raw]) {
    return STATUS_LABELS[raw];
  }
  if (VALUE_LABELS[raw]) {
    return VALUE_LABELS[raw];
  }
  return raw;
}

export function auditFieldLabel(key: string): string {
  if (FIELD_LABELS[key]) {
    return FIELD_LABELS[key];
  }
  return key
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Bytes → a short, readable size (e.g. "2.5 KB"), or "" when absent. */
function formatBytes(bytes: number | string | null | undefined): string {
  if (bytes === null || bytes === undefined || bytes === "") {
    return "";
  }
  const n = Number(bytes);
  if (!Number.isFinite(n) || n < 0) {
    return String(bytes);
  }
  if (n < 1024) {
    return `${n} B`;
  }
  const units = ["KB", "MB"];
  let value = n;
  let unit = "B";
  for (const next of units) {
    if (value < 1024) break;
    value /= 1024;
    unit = next;
  }
  const rounded = value >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${unit}`;
}

export function formatAuditValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length > 0
      ? value.map((item) => formatAuditValue(item)).join(", ")
      : "none";
  }
  if (value === null || value === undefined) {
    return "none";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "object") {
    return humanizeAuditObject(value as Record<string, unknown>);
  }
  return readableValue(value);
}

/** A short phrase for a nested object payload, never a raw JSON dump. */
export function humanizeAuditObject(
  value: Record<string, unknown>
): string {
  const order = value.order;
  const status = value.status;
  const role = value.role;
  if (status !== undefined) {
    // A stage/request object under a "Stage:" label; the status word alone
    // reads best ("Stage: Pending → Approved"), while role-only objects keep
    // their stage number ("Stage 1 supervisor").
    return readableValue(status);
  }
  if (order !== undefined && order !== null) {
    return `Stage ${order} ${readableValue(role ?? "step")}`;
  }
  if (value.name !== undefined) {
    return readableValue(value.name);
  }
  if (value.file_name !== undefined) {
    return readableValue(value.file_name);
  }
  if (value.reference_number !== undefined) {
    return readableValue(value.reference_number);
  }
  const entries = Object.entries(value).slice(0, MAX_PAIRS);
  return entries
    .map(([key, val]) => `${auditFieldLabel(key)}: ${auditChangesValue(val, key)}`)
    .join(", ");
}

/** Value formatter aware of the field it belongs to (bytes, size, etc.). */
function auditChangesValue(value: unknown, field: string): string {
  if (field === "file_size") {
    return formatBytes(value as number | string);
  }
  return formatAuditValue(value);
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

/** Pairs joined, with a leading reason kept front-and-centre (never clipped). */
function joinWithReason(reason: string, parts: string[]): string {
  const changes = joinPairs(parts);
  if (!reason) {
    return changes;
  }
  return changes ? `${truncate(reason)}, ${changes}` : truncate(reason);
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
    const parts = changes
      .map((field) => {
        const oldValue = diff.before[field];
        const newValue = diff.after[field];
        const display =
          oldValue !== undefined && oldValue !== null
            ? `${auditChangesValue(oldValue, field)} \u2192 ${auditChangesValue(newValue, field)}`
            : auditChangesValue(newValue, field);
        return { field, display };
      })
      // Skip pairs where the humanized value did not actually change, so an
      // approval that only bumped nested bookkeeping does not print noise like
      // "Request: Pending → Pending".
      .filter(({ field, display }) => {
        const oldValue = diff.before[field];
        const newValue = diff.after[field];
        if (oldValue !== undefined && oldValue !== null) {
          return (
            auditChangesValue(oldValue, field) !== auditChangesValue(newValue, field)
          );
        }
        return display !== "none";
      })
      .map(({ field, display }) => `${auditFieldLabel(field)}: ${truncate(display)}`);
    return joinWithReason(entry.reason, parts);
  }

  // Flat payload shape. `detail` is a free-form JSON bag, not always a diff:
  // `document_generated` records the file, `stage_skipped` the bypassed stages.
  // Reading those as a diff threw on `Object.keys(undefined)` and took the
  // whole audit page down, so they are summarised instead.
  if (entry.action === "document_generated") {
    const label = readableValue(detail.file_name);
    const size = formatBytes(detail.file_size as number | string | null | undefined);
    const text = `${label}${size ? ` (${size})` : ""}`;
    return text || entry.reason || "\u2014";
  }

  const parts = Object.entries(detail).map(
    ([key, value]) =>
      `${auditFieldLabel(key)}: ${truncate(auditChangesValue(value, key))}`
  );
  if (parts.length === 0) {
    return entry.reason || "\u2014";
  }
  // The payload has no `reason` key of its own, so the entry-level reason is
  // shown front-and-centre; `stage_skipped` keeps its payload reason instead.
  if (entry.reason && !("reason" in detail)) {
    return joinWithReason(entry.reason, parts);
  }
  return joinPairs(parts);
}
