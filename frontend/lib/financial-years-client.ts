import { apiErrorMessage } from "./utils";
import type {
  CarryOverResult,
  FinancialYear,
  FinancialYearInput,
  PublicHoliday,
  PublicHolidayInput,
} from "./financial-years";

export async function createFinancialYear(
  input: FinancialYearInput
): Promise<FinancialYear> {
  return proxyPost<FinancialYear>("/api/hr/financial-years", input);
}

export async function updateFinancialYear(
  id: number | string,
  input: FinancialYearInput
): Promise<FinancialYear> {
  return proxyPatch<FinancialYear>(`/api/hr/financial-years/${id}`, input);
}

/**
 * Rolls rejected-leave days from a financial year into the next one.
 *
 * Idempotent server-side: running it twice grants nothing the second time. The
 * result reports each employee's carried days, so the caller can show a summary.
 */
export async function runCarryOver(
  id: number | string
): Promise<CarryOverResult> {
  const response = await fetch(`/api/hr/financial-years/${id}/carry-over`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}

export async function createPublicHoliday(
  input: PublicHolidayInput
): Promise<PublicHoliday> {
  return proxyPost<PublicHoliday>("/api/hr/public-holidays", input);
}

export async function updatePublicHoliday(
  id: number | string,
  input: PublicHolidayInput
): Promise<PublicHoliday> {
  return proxyPatch<PublicHoliday>(`/api/hr/public-holidays/${id}`, input);
}

async function proxyPost<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}

async function proxyPatch<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}