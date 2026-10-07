import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { ApproverRoleTable } from "@/components/hr/approver-role-table";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import { listApproverRoles, listRoleAssignments } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";

const ROLES_ERROR = "Unable to load approver roles. Please try again.";
const HOLDERS_ERROR = "Unable to load who currently holds each role.";

async function RolesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  // One read, and only about the roles themselves. Who *holds* a role — at
  // any of the three scopes — is answered on the Approvers page, which is
  // where a holding is written; keeping a second copy of that list here would
  // be a second place to look and a second place to change it. The
  // *institution-wide* holders still travel with this page's rows, because
  // "an active institution-wide role with nobody holding it" is a stalled
  // application, and that is an alarm a roles screen must not be silent about.
  //
  // Retired roles stay on the page: HR needs to see that a role exists and why
  // it cannot be used, and a workflow may still name it.
  const [rolesResult, holdersResult] = await Promise.all([
    listApproverRoles(true).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
    ),
    listRoleAssignments().then(
      (assignments) => {
        const byRole = new Map<number, RoleAssignment[]>();
        for (const assignment of assignments) {
          const list = byRole.get(assignment.role) ?? [];
          list.push(assignment);
          byRole.set(assignment.role, list);
        }
        return { value: Object.fromEntries(byRole), error: "" };
      },
      () => ({ value: undefined, error: HOLDERS_ERROR })
    ),
  ]);

  const roles = rolesResult.value;
  const rolesError = rolesResult.error;
  const assignments = holdersResult.value;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Approver roles</h2>
          <p className="text-text-secondary">
            The approver positions a workflow step can name. Creating a role
            here is what makes it selectable on a chain; giving one person that
            position — at institution, team or campus scope — is done on the
            Approvers page.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/dashboard/hr-admin/approvers"
            className="inline-flex items-center gap-2 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Approvers
          </Link>
          <Link
            href="/dashboard/hr-admin/roles/new"
            className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            <Plus className="h-4 w-4" />
            New role
          </Link>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          All roles
        </h3>
        {rolesError && (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {rolesError}
          </div>
        )}
        {holdersResult.error && (
          <div className="mb-4 rounded-md bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected">
            {holdersResult.error} The holders column is hidden until the data
            loads again.
          </div>
        )}
        {!rolesError && (
          <ApproverRoleTable roles={roles} assignments={assignments} />
        )}
      </div>
    </div>
  );
}

export default RolesPage;
