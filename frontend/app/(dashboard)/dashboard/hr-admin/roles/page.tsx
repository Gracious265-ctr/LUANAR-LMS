import { redirect } from "next/navigation";


import { RolesSection } from "@/components/hr/RolesSection";
import { RoleAssignmentForm } from "@/components/hr/role-assignment-form";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import { listApproverRoles, listRoleAssignments } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import type { Employee } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";

const ROLES_ERROR = "Unable to load approver roles. Please try again.";
const HOLDERS_ERROR = "Unable to load institution-wide role holders.";

export default async function RolesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  // Three independent reads, issued together: roles, institution-wide holdings,
  // and the employees a holder can be chosen from. Each is reported separately
  // because each narrows a different thing HR can do on this page.
  //
  // Retired roles stay on the page: HR needs to see that a role exists and why
  // it cannot be used, and a workflow may still name it.
  const [rolesResult, holdersResult, employeesResult] = await Promise.all([
    listApproverRoles(true).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
    ),
    listRoleAssignments().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as RoleAssignment[], error: HOLDERS_ERROR })
    ),
    listAllEmployees().then(
      (value) => ({ value, error: "" }),
      () => ({
        value: [] as Employee[],
        error: "Unable to load employees, so holders cannot be added.",
      })
    ),
  ]);

  const roles = rolesResult.value;
  const rolesError = rolesResult.error;
  const holders = holdersResult.value;
  const holdersError = holdersResult.error;
  const employees = employeesResult.value;
  const employeesError = employeesResult.error;

  const holdersByRole: Record<number, RoleAssignment[]> = {};
  for (const assignment of holders) {
    (holdersByRole[assignment.role] ??= []).push(assignment);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Approver roles</h2>
        <p className="text-text-secondary">
          The approver positions a workflow stage can name. Team roles are
          staffed on the Teams page; institution-wide roles get a holder here.
        </p>
      </div>

      {rolesError ? (
        <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {rolesError}
        </div>
      ) : (
        <>
          {holdersError && (
            <p className="mb-3 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
              {holdersError}
            </p>
          )}
          <RolesSection roles={roles} assignments={holdersByRole} />

          {roles.length > 0 && !holdersError && !employeesError && (
            <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
              <h3 className="mb-4 text-lg font-semibold text-text-primary">
                Institution-wide holders
              </h3>
              {roles.some((role) => role.is_institution_wide && role.is_active) ? (
                <div className="space-y-4">
                  {roles
                    .filter((role) => role.is_institution_wide && role.is_active)
                    .map((role) => (
                      <div key={role.id}>
                        <p className="text-sm text-text-secondary">
                          {role.label}
                        </p>
                        <RoleAssignmentForm
                          role={role}
                          employees={employees}
                          assignments={holdersByRole[role.id] ?? []}
                        />
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">
                  No active institution-wide roles. Mark a role
                  institution-wide to give one person that position across
                  the whole university.
                </p>
              )}
              {employeesError && (
                <p className="mt-4 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
                  {employeesError}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
