import type { Department, DepartmentInput } from "./departments";
import { apiErrorMessage } from "./utils";

export async function createDepartment(
  input: DepartmentInput
): Promise<Department> {
  return send<Department>("/api/hr/departments", "POST", input);
}

export async function updateDepartment(
  id: number | string,
  input: DepartmentInput
): Promise<Department> {
  return send<Department>(`/api/hr/departments/${id}`, "PATCH", input);
}

/**
 * Retire a department.
 *
 * Retire, not delete: the backend refuses while a team or employee still
 * belongs to it, and answers with a sentence saying which. Keeping the row is
 * what lets a historical application still name a department it was routed
 * under.
 */
export async function retireDepartment(
  id: number | string
): Promise<Department> {
  return send<Department>(`/api/hr/departments/${id}/retire`, "POST");
}

async function send<T>(
  endpoint: string,
  method: "POST" | "PATCH",
  body?: unknown
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}
