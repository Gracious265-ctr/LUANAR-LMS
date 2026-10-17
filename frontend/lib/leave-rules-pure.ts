/**
 * Leave-rule vocabulary and pure helpers, in a module that never touches the
 * server.
 *
 * `lib/leave-rules.ts` reads Django through `api-client.ts`, which uses
 * `cookies` from `next/headers` and is therefore a server-only module. A client
 * component that imported `isAnnualLeaveType` or `leaveRuleStatus` from there
 * would put `next/headers` into the browser bundle and fail to compile. The
 * shapes and the pure predicates live here; the server module keeps the fetches
 * and re-exports this module so server callers keep one import path.
 */

import { currentDateIso } from "./utils";

export interface LeaveType {
  id: number;
  name: string;
  code: string;
  is_active?: boolean;
  /** May this type be scheduled ahead of time as a Leave Plan? */
  plannable?: boolean;
  /** Days before the start date a plan reminder fires; null means immediate. */
  plan_notice_days?: number | null;
}

export interface LeaveTypeInput {
  name: string;
  code?: string;
  is_active?: boolean;
  plannable?: boolean;
  plan_notice_days?: number | null;
}

export interface LeaveTypeListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: LeaveType[];
}

/**
 * Codes the canonical annual leave type is found under, matching the backend.
 *
 * Kept in step with `leave.services.find_annual_leave_type`: both codes are
 * recognised because a database written before the canonical code existed holds
 * annual leave under whichever one it was given.
 */
export const ANNUAL_LEAVE_CODES = ["annual", "annual-leave"];

/**
 * Whether a leave type is the canonical annual leave type, which an entitlement
 * provisions and which is therefore not editable from Leave Types.
 */
export function isAnnualLeaveType(
  leaveType: Pick<LeaveType, "code"> | null | undefined
): boolean {
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

export function leaveRuleStatus(
  rule: LeaveRule,
  today: string = currentDateIso()
): "current" | "upcoming" {
  return rule.effective_from <= today ? "current" : "upcoming";
}
