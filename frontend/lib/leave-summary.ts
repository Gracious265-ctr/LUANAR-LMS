import { apiClient } from "./api-client";

export interface LeaveSummaryProfile {
  grade: string;
  category: string | null;
  /** The team name, or null when the employee is on no team. */
  team: string | null;
  faculty: string | null;
  gender: string | null;
  appointment_date: string | null;
}

export interface LeaveSummaryEntitlement {
  days: number;
  effective_from: string;
}

export interface LeaveSummaryFinancialYear {
  label: string;
  start: string;
  end: string;
}

export interface LeaveSummaryUpcomingLeave {
  days: number;
  applications: number;
}

export interface LeaveSummary {
  profile: LeaveSummaryProfile | null;
  entitlement: LeaveSummaryEntitlement | null;
  financial_year: LeaveSummaryFinancialYear | null;
  available_balance: string | null;
  /** Days carried into the current year by a rejected-leave rollover. */
  carry_over_days: string | null;
  /** Applications still waiting on someone: submitted or rejected back to you. */
  pending_applications: number;
  /** Approved leave starting within the backend's upcoming window. */
  upcoming_leave: LeaveSummaryUpcomingLeave | null;
}

export async function getLeaveSummary(): Promise<LeaveSummary | null> {
  try {
    return await apiClient<LeaveSummary>("/api/v1/leave/me/summary/");
  } catch {
    return null;
  }
}