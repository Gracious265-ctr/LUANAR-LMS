/**
 * Leave Configuration vocabulary and pure helpers.
 *
 * Nothing here touches the network: the form's draft shape, its inline
 * validation (spec 3.3) and the labels the list renders all live in this
 * module so they can be reasoned about — and tested — without a fetch.
 * `lib/leave-config-client.ts` reads the API and re-uses these types.
 *
 * The backend owns every rule; this module only mirrors the shapes it sends
 * back. Per §1.3 there is deliberately no days-per-year field anywhere here —
 * entitlement is grade-based and lives in the Staff Members app.
 */

export type BranchScope = "academic" | "administrative" | "both";
export type GenderEligibility = "any" | "male" | "female";

export interface LeaveType {
  id: number;
  name: string;
  code: string;
  color: string;
  description: string;
  branch_scope: BranchScope;
  /** Grade ids, upper-cased; empty means every grade is eligible (§1.4). */
  eligible_grades: string[];
  eligible_gender: GenderEligibility;
  requires_supporting_document: boolean;
  max_duration_days: number | null;
  notice_days: number | null;
  eligibility: string;
  eligibility_rules: unknown[];
  consumes_annual_entitlement: boolean;
  plannable: boolean;
  requires_institutional_registrar_approval: boolean;
  /** §1.5 — retired by deactivation, never by deletion. */
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** The body a create/edit form submits. */
export interface LeaveTypeInput {
  name: string;
  code?: string;
  color: string;
  description: string;
  branch_scope: BranchScope;
  eligible_grades: string[];
  eligible_gender: GenderEligibility;
  requires_supporting_document: boolean;
  max_duration_days: number | null;
  notice_days: number | null;
  plannable: boolean;
  requires_institutional_registrar_approval: boolean;
}

/** One grade the eligibility multi-select offers. */
export interface GradeOption {
  id: string;
  name: string;
}

/**
 * The form's own state: everything typed as it is typed, with the two numeric
 * rules held as their raw input strings so a half-typed value never has to be
 * coerced back out of a number.
 */
export interface LeaveTypeDraft {
  name: string;
  code: string;
  color: string;
  description: string;
  branch_scope: BranchScope;
  eligible_grades: string[];
  eligible_gender: GenderEligibility;
  requires_supporting_document: boolean;
  /** Raw `<input type="number">` value; blank means "no maximum". */
  max_duration_days: string;
  /** Raw `<input type="number">` value; blank means "no minimum notice". */
  notice_days: string;
  plannable: boolean;
  requires_institutional_registrar_approval: boolean;
}

export type LeaveTypeField =
  | "name"
  | "code"
  | "max_duration_days"
  | "notice_days";

export type LeaveTypeFieldErrors = Partial<Record<LeaveTypeField, string>>;

export const BRANCH_SCOPE_OPTIONS: { value: BranchScope; label: string }[] = [
  { value: "both", label: "Both" },
  { value: "academic", label: "Academic" },
  { value: "administrative", label: "Administrative" },
];

export const GENDER_OPTIONS: { value: GenderEligibility; label: string }[] = [
  { value: "any", label: "Any" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

/**
 * The restricted palette (§3.3). Status-safe tokens only, so a chosen colour
 * can never clash with the badge/status colours used everywhere else in the
 * UI; hexes are carried here rather than composed into a class name because
 * Tailwind cannot see `bg-${color}-500` and would drop it from the bundle.
 */
export const LEAVE_TYPE_COLORS: { value: string; label: string; hex: string }[] =
  [
    { value: "blue", label: "Blue", hex: "#2563eb" },
    { value: "green", label: "Green", hex: "#16a34a" },
    { value: "red", label: "Red", hex: "#dc2626" },
    { value: "orange", label: "Orange", hex: "#ea580c" },
    { value: "yellow", label: "Yellow", hex: "#ca8a04" },
    { value: "purple", label: "Purple", hex: "#9333ea" },
    { value: "gray", label: "Gray", hex: "#6b7280" },
    { value: "indigo", label: "Indigo", hex: "#4f46e5" },
  ];

export const DEFAULT_LEAVE_TYPE_COLOR = "blue";

/**
 * Codes the canonical annual leave type is found under, matching the backend's
 * `leave_config.services.ANNUAL_LEAVE_CODES`. Both are recognised because a
 * database written before the canonical code existed holds annual leave under
 * whichever one it was given.
 */
export const ANNUAL_LEAVE_CODES = ["annual", "annual-leave"];

/**
 * Whether a leave type is the canonical annual leave type — provisioned by an
 * entitlement rather than typed by hand.
 *
 * Its *rules* are HR's to edit on the Leave Configuration form; only its
 * identity is pinned (the API refuses a rename, a code change and its
 * deactivation, because entitlements and the balance ledger resolve through
 * it).
 */
export function isAnnualLeaveType(
  leaveType: Pick<LeaveType, "code"> | null | undefined
): boolean {
  if (!leaveType?.code) return false;
  return ANNUAL_LEAVE_CODES.includes(leaveType.code.trim().toLowerCase());
}

export function branchScopeLabel(scope: BranchScope): string {
  return BRANCH_SCOPE_OPTIONS.find((option) => option.value === scope)?.label ?? scope;
}

export function genderLabel(gender: GenderEligibility): string {
  return GENDER_OPTIONS.find((option) => option.value === gender)?.label ?? gender;
}

/** Hex for a stored colour token, falling back to the default swatch. */
export function colorHex(color: string): string {
  return (
    LEAVE_TYPE_COLORS.find((option) => option.value === color)?.hex ??
    LEAVE_TYPE_COLORS.find(
      (option) => option.value === DEFAULT_LEAVE_TYPE_COLOR
    )!.hex
  );
}

/** `21 days`, `1 day`, or the wording for "no limit at all". */
export function dayCountLabel(days: number | null, none: string): string {
  if (days === null || days === undefined) return none;
  return days === 1 ? "1 day" : `${days} days`;
}

export function emptyLeaveTypeDraft(): LeaveTypeDraft {
  return {
    name: "",
    code: "",
    color: DEFAULT_LEAVE_TYPE_COLOR,
    description: "",
    branch_scope: "both",
    eligible_grades: [],
    eligible_gender: "any",
    requires_supporting_document: false,
    max_duration_days: "",
    notice_days: "",
    plannable: true,
    requires_institutional_registrar_approval: false,
  };
}

export function leaveTypeToDraft(leaveType: LeaveType): LeaveTypeDraft {
  return {
    name: leaveType.name,
    code: leaveType.code,
    color: leaveType.color || DEFAULT_LEAVE_TYPE_COLOR,
    description: leaveType.description ?? "",
    branch_scope: leaveType.branch_scope ?? "both",
    eligible_grades: leaveType.eligible_grades ?? [],
    eligible_gender: leaveType.eligible_gender ?? "any",
    requires_supporting_document: leaveType.requires_supporting_document,
    max_duration_days:
      leaveType.max_duration_days === null ? "" : String(leaveType.max_duration_days),
    notice_days:
      leaveType.notice_days === null ? "" : String(leaveType.notice_days),
    plannable: leaveType.plannable,
    requires_institutional_registrar_approval:
      leaveType.requires_institutional_registrar_approval,
  };
}

/**
 * Inline validation for the create/edit form (spec 3.3): a required name, and
 * numeric fields that reject negative values — with max duration additionally
 * having to be positive. Nothing cross-field; the backend remains the
 * authority on uniqueness and on the reserved annual-leave identity.
 */
export function validateLeaveTypeDraft(
  draft: LeaveTypeDraft
): LeaveTypeFieldErrors {
  const errors: LeaveTypeFieldErrors = {};

  if (!draft.name.trim()) {
    errors.name = "Name is required.";
  }

  const maxDuration = draft.max_duration_days.trim();
  if (maxDuration) {
    const value = Number(maxDuration);
    if (!Number.isInteger(value) || value < 1) {
      errors.max_duration_days = "Maximum duration must be a whole number of at least 1 day.";
    }
  }

  const notice = draft.notice_days.trim();
  if (notice) {
    const value = Number(notice);
    if (!Number.isInteger(value) || value < 0) {
      errors.notice_days =
        "Notice period must be a whole number of days and cannot be negative.";
    }
  }

  return errors;
}

/** Turns a validated draft into the body the API accepts. */
export function draftToInput(draft: LeaveTypeDraft): LeaveTypeInput {
  const maxDuration = draft.max_duration_days.trim();
  const notice = draft.notice_days.trim();

  return {
    name: draft.name.trim(),
    code: draft.code.trim() || undefined,
    color: draft.color,
    description: draft.description.trim(),
    branch_scope: draft.branch_scope,
    // Dropped rather than rejected: the API normalises the same way, and a
    // stray blank in the multi-select should not block an otherwise valid save.
    eligible_grades: draft.eligible_grades
      .map((grade) => grade.trim())
      .filter(Boolean),
    eligible_gender: draft.eligible_gender,
    requires_supporting_document: draft.requires_supporting_document,
    max_duration_days: maxDuration === "" ? null : Number(maxDuration),
    notice_days: notice === "" ? null : Number(notice),
    plannable: draft.plannable,
    // Still sent when the control is hidden (an academic type): the value is
    // stored either way, and the org-tree rule already makes it inert for
    // academic chains. Hiding the control must never quietly clear the flag.
    requires_institutional_registrar_approval:
      draft.requires_institutional_registrar_approval,
  };
}

/**
 * Maps a DRF error body onto the fields that can show it inline.
 *
 * A field error may arrive as a string or a one-element list; anything else —
 * `non_field_errors`, an unrecognised key — is left to the caller's
 * form-level banner rather than being swallowed.
 */
export function leaveTypeFieldErrors(data: unknown): LeaveTypeFieldErrors {
  const errors: LeaveTypeFieldErrors = {};
  if (!data || typeof data !== "object") return errors;

  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (!(key === "name" || key === "code" || key === "max_duration_days" || key === "notice_days")) {
      continue;
    }
    const message = Array.isArray(value) ? value[0] : value;
    if (typeof message === "string" && message) {
      errors[key as LeaveTypeField] = message;
    }
  }
  return errors;
}

/** The form-level message out of a DRF error body, when there is one. */
export function leaveTypeFormError(data: unknown): string {
  if (!data || typeof data !== "object") return "";
  const record = data as Record<string, unknown>;
  const nonField = Array.isArray(record.non_field_errors)
    ? record.non_field_errors[0]
    : record.non_field_errors;
  if (typeof nonField === "string" && nonField) return nonField;
  return "";
}
