import type { BadgeTone } from "@/components/ui/badge";

import { apiClientUrl } from "./api-client";

/**
 * The "On Leave" read model, as the backend scopes it.
 *
 * The scope is not decided here: the endpoint answers with the rows the signed-in
 * person may read and the rung of the ladder they stand on, so this module only
 * carries the shape across and names the states a row can be in.
 */
export type OnLeaveState = "on_leave" | "upcoming" | "returned";

/** The visibility rungs, widest first. */
export type OnLeaveScopeKind =
  | "organisation"
  | "institution"
  | "campus"
  | "team"
  | "chain"
  | "self";

export interface OnLeaveEmployee {
  id: number;
  full_name: string;
  designation: string;
  team: string;
  campus: string;
}

export interface OnLeaveLeaveType {
  id: number | null;
  name: string;
}

export interface OnLeaveRow {
  id: string;
  reference_number: string | null;
  employee: OnLeaveEmployee;
  leave_type: OnLeaveLeaveType;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  state: OnLeaveState;
}

export interface OnLeaveScope {
  kind: OnLeaveScopeKind;
  label: string;
  description: string;
}

export interface OnLeaveCounts {
  on_leave: number;
  upcoming: number;
  returned: number;
}

export interface OnLeaveData {
  /** The day the states were calculated against, as `yyyy-MM-dd`. */
  today: string;
  scope: OnLeaveScope;
  counts: OnLeaveCounts;
  results: OnLeaveRow[];
}

export interface OnLeaveFilters {
  /** A name or email fragment, capped by the backend. */
  q?: string;
  /** Add returned leave after the current and upcoming rows. */
  includePast?: boolean;
}

/** Label and badge tone per state — the three words a row can wear. */
export const ON_LEAVE_STATE: Record<
  OnLeaveState,
  { label: string; tone: BadgeTone }
> = {
  on_leave: { label: "On leave", tone: "approved" },
  upcoming: { label: "Upcoming", tone: "info" },
  returned: { label: "Returned", tone: "neutral" },
};

/** The On Leave URL for a set of filters, for a link or a fetch. */
export function onLeaveUrl(filters: OnLeaveFilters = {}): string {
  const params = new URLSearchParams();
  const search = filters.q?.trim();
  if (search) params.set("q", search);
  if (filters.includePast) params.set("include_past", "true");
  const query = params.toString();
  return `/api/v1/leave/on-leave/${query ? `?${query}` : ""}`;
}

export async function getOnLeave(
  filters: OnLeaveFilters = {}
): Promise<OnLeaveData> {
  return apiClientUrl<OnLeaveData>(onLeaveUrl(filters));
}
