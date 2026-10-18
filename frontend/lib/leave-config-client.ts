import { apiErrorMessage } from "./utils";
import type { GradeOption, LeaveType, LeaveTypeInput } from "./leave-config";

/**
 * The Leave Configuration API, read through the `/api/leave-config/*` proxy
 * routes so the JWT cookie handling stays in one place (the same arrangement
 * `lib/leave-rules-client.ts` used before unit 06 retired it).
 *
 * Failures are thrown as {@link LeaveConfigRequestError} rather than a bare
 * `Error`, because the form shows a DRF field error next to the field it
 * belongs to and a generic banner only when there is no field to blame.
 */
export class LeaveConfigRequestError extends Error {
  /** The raw DRF error body, e.g. `{ name: ["A leave type … already exists."] }`. */
  readonly data: unknown;

  constructor(message: string, data: unknown) {
    super(message);
    this.name = "LeaveConfigRequestError";
    this.data = data;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`/api/leave-config/${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new LeaveConfigRequestError(
      apiErrorMessage(data) || "An error occurred. Please try again.",
      data
    );
  }
  return data as T;
}

export async function listLeaveTypes(
  options: { includeInactive?: boolean } = {}
): Promise<LeaveType[]> {
  const query = options.includeInactive ? "?include_inactive=true" : "";
  return request<LeaveType[]>("GET", `types/${query}`);
}

export async function getLeaveType(id: number | string): Promise<LeaveType> {
  return request<LeaveType>("GET", `types/${id}/`);
}

export async function createLeaveType(input: LeaveTypeInput): Promise<LeaveType> {
  return request<LeaveType>("POST", "types/", input);
}

export async function updateLeaveType(
  id: number | string,
  input: LeaveTypeInput
): Promise<LeaveType> {
  return request<LeaveType>("PATCH", `types/${id}/`, input);
}

export async function deactivateLeaveType(id: number | string): Promise<LeaveType> {
  return request<LeaveType>("POST", `types/${id}/deactivate/`);
}

export async function reactivateLeaveType(id: number | string): Promise<LeaveType> {
  return request<LeaveType>("POST", `types/${id}/reactivate/`);
}

/** The grade ids the eligibility multi-select labels (§1.4). */
export async function listGrades(): Promise<GradeOption[]> {
  return request<GradeOption[]>("GET", "grades/");
}
