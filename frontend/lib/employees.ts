import { apiClient, apiClientUrl } from "./api-client";

export type EmployeeCategory = "academic" | "administration";

/**
 * What an account can reach, not a place in an approval chain.
 *
 * Approver status is held as data — a team membership or an institution-wide
 * holding — and read back as `approver_roles`.
 */
export type UserRole = "employee" | "approver" | "hr";

export interface TeamOption {
  id: number;
  name: string;
  status: string;
  /**
   * False when the team is not routing today, so the picker can say so next to
   * the name. Assigning somebody to a team that will not route is a trap: the
   * employee only finds out when they submit.
   */
  is_effective: boolean;
}

export interface Employee {
  id: number;
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  /** Approver positions this person holds, by code. Empty for an employee. */
  approver_roles: string[];
  designation: string;
  department: string;
  category: EmployeeCategory;
  grade: string;
  appointment_date: string | null;
  /** The team whose approval chain this employee submits into. */
  team: number | null;
  team_name: string;
  is_active: boolean;
}

export interface EmployeeInput {
  email: string;
  first_name: string;
  last_name: string;
  role?: UserRole;
  designation?: string;
  department?: string;
  category?: EmployeeCategory;
  grade?: string;
  appointment_date?: string | null;
  team?: number | null;
  is_active?: boolean;
}

export interface EmployeeListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Employee[];
}

export async function listEmployees(search = ""): Promise<EmployeeListResponse> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiClient<EmployeeListResponse>(`/api/v1/employees/${query}`);
}

/**
 * Every employee, for a picker that has to be exhaustive.
 *
 * `listEmployees` answers one page, which is right for a table and wrong for a
 * "choose somebody" list: a page-1-only read would silently offer the first few
 * employees and look to HR like the rest had no accounts.
 */
export async function listAllEmployees(): Promise<Employee[]> {
  const first = await listEmployees();
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiClientUrl<EmployeeListResponse>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}

export async function getEmployee(id: number | string): Promise<Employee> {
  return apiClient<Employee>(`/api/v1/employees/${id}/`);
}