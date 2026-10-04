import { apiClient } from "./api-client";
import { currentDateIso } from "./utils";

export interface Entitlement {
  id: number;
  grade_start: string;
  grade_end: string;
  days: number;
  effective_from: string;
  leave_type: number | null;
  leave_type_name?: string | null;
}

export interface EntitlementInput {
  grade_start: string;
  grade_end: string;
  days: number;
  effective_from: string;
  leave_type: number | null;
}

export interface EntitlementResolution {
  grade: string;
  days: number | null;
  effective_from: string | null;
}

export interface EntitlementListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Entitlement[];
}

export async function listEntitlements(): Promise<EntitlementListResponse> {
  return apiClient<EntitlementListResponse>("/api/v1/entitlements/");
}

export async function getEntitlement(
  id: number | string
): Promise<Entitlement> {
  return apiClient<Entitlement>(`/api/v1/entitlements/${id}/`);
}

export async function resolveEntitlement(
  grade: string
): Promise<EntitlementResolution> {
  return apiClient<EntitlementResolution>(
    `/api/v1/entitlements/resolve/?grade=${encodeURIComponent(grade)}`
  );
}

export function expandGradeRange(start: string, end: string): string[] {
  if (start.length === 1 && end.length === 1) {
    const startCode = start.charCodeAt(0);
    const endCode = end.charCodeAt(0);
    if (startCode <= endCode) {
      const grades: string[] = [];
      for (let code = startCode; code <= endCode; code++) {
        grades.push(String.fromCharCode(code));
      }
      return grades;
    }
  }
  return [start, end];
}

export function gradeOptionsFromEntitlements(
  entitlements: Entitlement[],
  today: string = currentDateIso()
): string[] {
  const grades = new Set<string>();
  for (const rule of entitlements) {
    if (rule.effective_from <= today) {
      for (const grade of expandGradeRange(rule.grade_start, rule.grade_end)) {
        grades.add(grade);
      }
    }
  }
  return Array.from(grades).sort();
}