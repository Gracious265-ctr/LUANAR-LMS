/**
 * Client-side shapes for Leave Plans (refinement unit 04).
 *
 * Mirrors the backend serializer contract (`plans/serializers.py`): the read
 * serializer flattens the plan's foreign keys into stable name/id pairs, so the
 * calendar and cards never have to fetch a leave type or a financial year.
 */

export type LeavePlanStatus =
  | "upcoming"
  | "notified"
  | "missed"
  | "converted"
  | "cancelled";

export interface LeavePlan {
  id: string;
  employee_name: string;
  leave_type_id: number;
  leave_type_name: string;
  financial_year_label: string;
  planned_start_date: string;
  planned_end_date: string;
  notes: string;
  status: LeavePlanStatus;
  notified_at: string | null;
  follow_up_sent_at: string | null;
  /** The draft application this plan produced, once converted. */
  converted_application: string | null;
  created_at: string;
  updated_at: string;
  /** Non-blocking overlap note, present only on create/update responses. */
  overlap_warning?: string;
}

/** A calendar scope token the requester may select (`PlanScopeSerializer`). */
export interface PlanScope {
  id: string;
  label: string;
}

/** Body of `POST /plans/{id}/apply/` (`PlanApplicationSerializer`). */
export interface PlanApplicationResult {
  application_id: string;
}

/** Paginated `GET /plans/` list. */
export interface PlanListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: LeavePlan[];
}

/** `GET /plans/team/` payload. */
export interface TeamPlansResponse {
  scope: PlanScope;
  month_start: string;
  month_end: string;
  results: LeavePlan[];
}

/** Body accepted by `POST /plans/` (`LeavePlanWriteSerializer`). */
export interface CreatePlanInput {
  leave_type: number;
  financial_year?: number;
  planned_start_date: string;
  planned_end_date: string;
  notes?: string;
}
