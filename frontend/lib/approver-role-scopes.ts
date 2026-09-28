/**
 * How much of an applicant's leave history an approver role may see.
 *
 * Deliberately free of imports: the roles list, the workflow form, and the role
 * form are all client components, and a constant that a client component reads
 * cannot live in the same module as the server-side API reader.
 */
export const HISTORY_SCOPES = [
  "all",
  "same_department",
  "same_faculty",
  "current_financial_year",
  "none",
] as const;

export type HistoryScope = (typeof HISTORY_SCOPES)[number];

export const HISTORY_SCOPE_LABELS: Record<HistoryScope, string> = {
  all: "Full history",
  same_department: "Same department only",
  same_faculty: "Same faculty only",
  current_financial_year: "Current financial year only",
  none: "No history",
};

/**
 * The label for a history scope, falling back to the stored value.
 *
 * The fallback is deliberate: a scope added to the backend after this build
 * must render as itself rather than as `undefined` or by crashing.
 */
export function historyScopeLabel(scope: string): string {
  return HISTORY_SCOPE_LABELS[scope as HistoryScope] ?? scope;
}
