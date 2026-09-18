import { apiErrorMessage } from "./utils";
import type {
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