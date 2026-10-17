/**
 * Test fixtures for Leave Plans (refinement unit 04).
 *
 * Factory functions rather than frozen literals: each test states only the
 * fields it cares about, so a status test does not repeat a whole plan and a
 * contract change lands in one place.
 */

import type {
  LeavePlan,
  PlanScope,
  TeamPlansResponse,
} from "../types";

export function makePlan(over: Partial<LeavePlan> = {}): LeavePlan {
  return {
    id: "plan-1",
    employee_name: "Tiwonge Banda",
    leave_type_id: 1,
    leave_type_name: "Annual Leave",
    financial_year_label: "2026-27",
    planned_start_date: "2026-11-02",
    planned_end_date: "2026-11-06",
    notes: "",
    status: "upcoming",
    notified_at: null,
    follow_up_sent_at: null,
    converted_application: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
    ...over,
  };
}

export function makeScope(over: Partial<PlanScope> = {}): PlanScope {
  return { id: "team:1", label: "Finance", ...over };
}

export function makeTeamPlans(
  over: Partial<TeamPlansResponse> = {}
): TeamPlansResponse {
  return {
    scope: makeScope(),
    month_start: "2026-11-01",
    month_end: "2026-11-30",
    results: [],
    ...over,
  };
}
