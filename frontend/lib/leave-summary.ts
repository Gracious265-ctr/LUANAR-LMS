import { apiClient } from "./api-client";

export interface LeaveSummaryProfile {
  grade: string;
  category: string | null;
  department: string;
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

export interface LeaveSummary {
  profile: LeaveSummaryProfile | null;
  entitlement: LeaveSummaryEntitlement | null;
  financial_year: LeaveSummaryFinancialYear | null;
  available_balance: string | null;
}

export async function getLeaveSummary(): Promise<LeaveSummary | null> {
  try {
    return await apiClient<LeaveSummary>("/api/v1/leave/me/summary/");
  } catch {
    return null;
  }
}