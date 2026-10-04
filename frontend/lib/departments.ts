import { apiClientUrl } from "./api-client";

/**
 * A department, as the API reports it.
 *
 * A department is reference data HR maintains, not free text typed into a team
 * form: whether somebody may be appointed as a team's approver *is* a comparison
 * of two department ids, so a typed string could not be compared to anything.
 * That is why the team's own field is a pick from here.
 */
export interface Department {
  id: number;
  name: string;
  is_active: boolean;
  /** Teams inside this department, flattened so a list renders without a second read. */
  team_count: number;
  employee_count: number;
  teams: { id: number; name: string; status: string }[];
  created_at: string;
  updated_at: string;
}

export interface DepartmentInput {
  name: string;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  results: T[];
}

/**
 * Read a whole paginated list, not its first page.
 *
 * A department picker built from page one would quietly offer fewer departments
 * than exist, and the ones left out would look to HR like they were never
 * configured.
 */
async function readAllPages<T>(endpoint: string): Promise<T[]> {
  const first = await apiClientUrl<Paginated<T>>(endpoint);
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiClientUrl<Paginated<T>>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}

export async function listDepartments(includeRetired = false): Promise<Department[]> {
  const query = includeRetired ? "?include_retired=1" : "";
  return readAllPages<Department>(`/api/v1/departments/${query}`);
}

/** The name of a department id, for a label beside an id that has already been chosen. */
export function departmentName(
  departments: Department[],
  id: number | null | undefined
): string {
  if (id === null || id === undefined) return "";
  return departments.find((department) => department.id === id)?.name ?? "";
}