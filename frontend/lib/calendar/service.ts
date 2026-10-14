import type { TeamCalendarResponse } from "./types";

export type TeamCalendarResult =
  | { ok: true; data: TeamCalendarResponse }
  | { ok: false; kind: "not_found" | "error"; message: string };

const FETCH_ERROR =
  "Could not reach the server. Check your connection and try again.";

/**
 * One team's leave for one month (spec 3.1).
 *
 * A 404 is the only "you may not see this" the API gives, by design: the
 * backend answers 404 for both a missing team and one outside the caller's
 * reach, so a team's existence cannot be probed.
 */
export async function fetchTeamCalendar(
  unitId: number,
  month: string
): Promise<TeamCalendarResult> {
  const params = new URLSearchParams({
    unit_id: String(unitId),
    month,
  });
  try {
    const res = await fetch(`/api/leave/calendar/team/?${params.toString()}`, {
      credentials: "include",
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: "This team's calendar is not available to you.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message:
          (data.detail as string) || "Failed to load the team calendar.",
      };
    }
    return { ok: true, data: data as TeamCalendarResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}
