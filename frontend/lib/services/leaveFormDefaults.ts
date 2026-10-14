/**
 * Warm-start values for the leave application form (spec §3.6).
 *
 * The backend derives the employee's most-recent type, the next working day,
 * and the remaining balance per annual-deducting type. Everything is advisory:
 * the form pre-selects and pre-fills but never locks, and a failure simply
 * leaves the form at its blank defaults.
 */
export interface LeaveFormDefaults {
  last_leave_type_id: number | null;
  default_start_date: string | null;
  balance_by_type: Record<string, string>;
}

export async function getLeaveFormDefaults(): Promise<LeaveFormDefaults> {
  const res = await fetch("/api/leave/me/form-defaults/");
  if (!res.ok) {
    throw new Error("Failed to load form defaults");
  }
  return (await res.json()) as LeaveFormDefaults;
}
