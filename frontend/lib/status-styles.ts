/**
 * The one place status → colour is defined (spec 3.4).
 *
 * Keys are the four semantic application statuses from ui-context.md, plus a
 * neutral `notice` tone reused for warning surfaces. The
 * chip string mirrors the spec's `STATUS_STYLES` shape — background, text and
 * border *colour* — deliberately without a border-width class: call sites that
 * draw a bordered surface add `border` (or `border-l-2`) themselves, so a
 * plain badge stays exactly as it always rendered while every bordered
 * surface picks up the same tinted hairline.
 *
 * Derivations, so the remaining display forms never restate a token:
 * - `STATUS_TEXT` — text colour only (status sentences, table cells).
 * - `STATUS_SOLID` — solid fill (timeline dots, stepper markers, toasts).
 * - `STATUS_BORDER` — the `/30` tinted hairline for panel edges.
 *
 * Status *badges*, *alerts* and the label maps in `lib/*\/labels.ts` all
 * import from this file; a new status needs one entry here plus its badge
 * tone, nothing else.
 */

export const STATUS_STYLES = {
  pending:
    "bg-status-pending-subtle text-status-pending border-status-pending/30",
  approved:
    "bg-status-approved-subtle text-status-approved border-status-approved/30",
  rejected:
    "bg-status-rejected-subtle text-status-rejected border-status-rejected/30",
  notice:
    "bg-status-notice-subtle text-status-notice border-status-notice/30",
  cancelled:
    "bg-status-cancelled-subtle text-status-cancelled border-status-cancelled/30",
} as const;

export type StatusKey = keyof typeof STATUS_STYLES;

export const STATUS_TEXT = {
  pending: "text-status-pending",
  approved: "text-status-approved",
  rejected: "text-status-rejected",
  notice: "text-status-notice",
  cancelled: "text-status-cancelled",
} as const satisfies Record<StatusKey, string>;

export const STATUS_SOLID = {
  pending: "bg-status-pending",
  approved: "bg-status-approved",
  rejected: "bg-status-rejected",
  notice: "bg-status-notice",
  cancelled: "bg-status-cancelled",
} as const satisfies Record<StatusKey, string>;

export const STATUS_BORDER = {
  pending: "border-status-pending/30",
  approved: "border-status-approved/30",
  rejected: "border-status-rejected/30",
  notice: "border-status-notice/30",
  cancelled: "border-status-cancelled/30",
} as const satisfies Record<StatusKey, string>;
