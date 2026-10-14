import { apiClient } from "./api-client";
import type {
  LeaveRule,
  LeaveRuleListResponse,
  LeaveRuleQuery,
  LeaveType,
  LeaveTypeListResponse,
} from "./leave-rules-pure";

// The vocabulary and pure predicates are client-safe and live beside this
// module, not inside it: this file reads Django through `api-client`, which is
// server-only, and a client component that imported `isAnnualLeaveType` from
// here would put `next/headers` into the browser bundle. Re-exported so server
// callers and existing tests keep one import path.
export {
  ANNUAL_LEAVE_CODES,
  isAnnualLeaveType,
  leaveRuleStatus,
  type EffectiveFilter,
  type LeaveRule,
  type LeaveRuleInput,
  type LeaveRuleListResponse,
  type LeaveRuleQuery,
  type LeaveType,
  type LeaveTypeInput,
  type LeaveTypeListResponse,
} from "./leave-rules-pure";

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
