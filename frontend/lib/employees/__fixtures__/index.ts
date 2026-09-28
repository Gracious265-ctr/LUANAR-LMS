import type { Employee, EmployeeCategory, UserRole } from "@/lib/employees";

/**
 * An employee record as the API reports it.
 *
 * `approver_roles` is what makes somebody an approver — a team membership or an
 * institution-wide holding, reported as codes — and it is independent of
 * `role`, which only records what the account can reach. A test that needs an
 * approver sets `approver_roles`; setting `role` alone is not enough.
 */
export function makeEmployee(
  overrides: Partial<Employee> = {}
): Employee {
  return {
    id: 1,
    user_id: 1,
    email: "employee@test.luanar",
    first_name: "Test",
    last_name: "Employee",
    full_name: "Test Employee",
    role: "employee" as UserRole,
    approver_roles: [],
    designation: "Lecturer",
    department: "Bunda College",
    category: "academic" as EmployeeCategory,
    grade: "G",
    appointment_date: "2020-01-01",
    team: null,
    team_name: "",
    is_active: true,
    ...overrides,
  };
}
