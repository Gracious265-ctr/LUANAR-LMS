import { apiClient } from "./api-client";
import { currentDateIso } from "./utils";

export interface FinancialYear {
  id: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface FinancialYearInput {
  start_date: string;
  end_date: string;
  is_active?: boolean;
}

export interface FinancialYearListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FinancialYear[];
}

/** One employee's carry-over outcome from a rejected-leave rollover. */
export interface CarryOverEmployee {
  employee_id: number;
  days: string;
  /** True when this rollover created the row; false when it already existed. */
  created: boolean;
}

/** The result of running (or previewing) a rejected-leave rollover. */
export interface CarryOverResult {
  from_financial_year: string;
  to_financial_year: string;
  dry_run: boolean;
  employees: CarryOverEmployee[];
  total_days: string;
}

export interface PublicHoliday {
  id: number;
  name: string;
  date: string;
}
export interface PublicHolidayInput {
  name: string;
  date: string;
}

export interface PublicHolidayListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: PublicHoliday[];
}

export async function listFinancialYears(): Promise<FinancialYearListResponse> {
  return apiClient<FinancialYearListResponse>("/api/v1/financial-years/");
}

export async function getFinancialYear(
  id: number | string
): Promise<FinancialYear> {
  return apiClient<FinancialYear>(`/api/v1/financial-years/${id}/`);
}

export async function listPublicHolidays(
  year?: number | string
): Promise<PublicHolidayListResponse> {
  const qs = year ? `?year=${encodeURIComponent(String(year))}` : "";
  return apiClient<PublicHolidayListResponse>(`/api/v1/public-holidays/${qs}`);
}

export async function getPublicHoliday(
  id: number | string
): Promise<PublicHoliday> {
  return apiClient<PublicHoliday>(`/api/v1/public-holidays/${id}/`);
}

export function financialYearStatus(
  year: FinancialYear,
  today: string = currentDateIso()
): "active" | "upcoming" | "past" {
  if (year.is_active) {
    return "active";
  }
  if (year.start_date > today) {
    return "upcoming";
  }
  return "past";
}