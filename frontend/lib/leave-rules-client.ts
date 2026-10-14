import { apiErrorMessage } from "./utils";
import type {
  LeaveRule,
  LeaveRuleInput,
  LeaveType,
  LeaveTypeInput,
} from "./leave-rules";

export async function createLeaveType(input: LeaveTypeInput): Promise<LeaveType> {
  return proxyPost<LeaveType>("/api/hr/leave-types", input);
}

export async function updateLeaveType(
  id: number | string,
  input: LeaveTypeInput
): Promise<LeaveType> {
  return proxyPatch<LeaveType>(`/api/hr/leave-types/${id}`, input);
}

export async function createLeaveRule(input: LeaveRuleInput): Promise<LeaveRule> {
  return proxyPost<LeaveRule>("/api/hr/leave-rules", input);
}

export async function updateLeaveRule(
  id: number | string,
  input: LeaveRuleInput
): Promise<LeaveRule> {
  return proxyPatch<LeaveRule>(`/api/hr/leave-rules/${id}`, input);
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
