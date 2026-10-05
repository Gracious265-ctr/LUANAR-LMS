import { apiClient } from "./api-client";
import { currentDateIso } from "./utils";

export interface LeaveType {
  id: number;
  name: string;
  code: string;
  is_active?: boolean;
}

export interface LeaveTypeInput {
  name: string;
  code?: string;
  is_active?: boolean;
}

export interface LeaveTypeListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: LeaveType[];
}

/** Codes the canonical annual leave type is found under, matching the backend. */
export const ANNUAL_LEAVE_CODES = ["annual", "annual-leave"];

/**
 * Whether a leave type is the canonical annual leave type, which an entitlement
 * provisions and which is therefore not editable from Leave Types.
 *
 * Kept in step with `leave.services.find_annual_leave_type`: both codes are
 * recognised because a database written before the canonical code existed holds
 * annual leave under whichever one it was given.
 */
export function isAnnualLeaveType(leaveType: Pick<LeaveType, "code"> | null | undefined): boolean {
  if (!leaveType?.code) return false;
  return ANNUAL_LEAVE_CODES.includes(leaveType.code.trim().toLowerCase());
}

export interface LeaveRule {
  id: number;
  leave_type: number;
  leave_type_code: string;
  leave_type_name: string;
  max_duration_days: number;
  eligibility: string;
  min_notice_days: number;
  requires_supporting_document: boolean;
  consumes_annual_entitlement: boolean;
  effective_from: string;
}

export interface LeaveRuleInput {
  leave_type: number;
  max_duration_days: number;
  eligibility?: string;
  min_notice_days?: number;
  requires_supporting_document?: boolean;
  consumes_annual_entitlement?: boolean;
  effective_from: string;
}

export interface LeaveRuleListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: LeaveRule[];
}

export type EffectiveFilter = "current" | "upcoming" | "all";

export interface LeaveRuleQuery {
  leave_type?: number | string;
  effective?: EffectiveFilter;
}

export async function listLeaveTypes(): Promise<LeaveTypeListResponse> {
  return apiClient<LeaveTypeListResponse>("/api/v1/leave-types/");
}

export async function getLeaveType(id: number | string): Promise<LeaveType> {
  return apiClient<LeaveType>(`/api/v1/leave-types/${id}/`);
}

export async function listLeaveRules(
  params: LeaveRuleQuery = {}
): Promise<LeaveRuleListResponse> {
  const query = new URLSearchParams();
  if (params.leave_type) {
    query.set("leave_type", String(params.leave_type));
  }
  if (params.effective && params.effective !== "all") {
    query.set("effective", params.effective);
  }
  const qs = query.toString();
  return apiClient<LeaveRuleListResponse>(
    `/api/v1/leave-rules/${qs ? `?${qs}` : ""}`
  );
}

export async function getLeaveRule(id: number | string): Promise<LeaveRule> {
  return apiClient<LeaveRule>(`/api/v1/leave-rules/${id}/`);
}

export function leaveRuleStatus(
  rule: LeaveRule,
  today: string = currentDateIso()
): "current" | "upcoming" {
  return rule.effective_from <= today ? "current" : "upcoming";
}