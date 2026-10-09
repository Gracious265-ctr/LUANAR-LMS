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
  /**
   * The password this person signs in with. Required on create; on edit a blank
   * or absent value keeps the current one. Never read back from the API.
   */
  password?: string;
  role?: UserRole;
  designation?: string;
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
 *
 * `category` scopes the read to one half of the institution, the same way a
 * team's roster is scoped: a team-wide approver must match the team's category
 * and a campus-wide approver must be academic, so the picker reads only the
 * category the write will accept.
 */
export function listAllEmployees(
  category?: EmployeeCategory
): Promise<Employee[]> {
  const query = category ? `?category=${category}` : "";
  return listAllPages(query);
}

export async function getEmployee(id: number | string): Promise<Employee> {
  return apiClient<Employee>(`/api/v1/employees/${id}/`);
}

/**
 * The normal employees whose leave routes through a team.
 *
 * This is the roster that stands beside the approval chain: the approvers decide
 * a submission, and these are the people whose submissions that chain decides.
 * Read through the appointment filter, never by loading everyone and matching in
 * the browser, so the list stays correct as the directory grows.
 */
export function listEmployeesByTeam(
  teamId: number | string
): Promise<Employee[]> {
  return listAllPages(`?team=${teamId}`);
}

/**
 * The employees who are not on any team yet.
 *
 * The candidates for a team's roster, kept as a server-side filter rather than by
 * subtracting one client-side list from another: a person on another team is not
 * simply "free", and quietly reassigning them from this screen would hide that
 * decision from the team they are leaving.
 *
 * The list is scoped to a team's own half of the institution: `category` keeps
 * only employees of the team's kind (an academic team takes academic employees,
 * an administration team takes administration employees), and
 * `excludedWideForTeam` drops the people who staff that team's steps as wide
 * approvers — an approver is managed on the Approvers tab, not the roster.
 */
export function listUnassignedEmployees(
  category?: EmployeeCategory,
  excludedWideForTeam?: number | string
): Promise<Employee[]> {
  const params = new URLSearchParams({ team: "none" });
  if (category) params.set("category", category);
  if (excludedWideForTeam !== undefined) {
    params.set("not_wide_for_team", String(excludedWideForTeam));
  }
  return listAllPages(`?${params.toString()}`);
}

async function listAllPages(query: string): Promise<Employee[]> {
  const first = await apiClient<EmployeeListResponse>(
    `/api/v1/employees/${query}`
  );
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiClientUrl<EmployeeListResponse>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}