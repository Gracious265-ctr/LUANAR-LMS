import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { ApproverRoleTable } from "@/components/hr/approver-role-table";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";

const ROLES_ERROR = "Unable to load approver roles. Please try again.";

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
  // be a second place to look and a second place to change it.
  //
  // Retired roles stay on the page: HR needs to see that a role exists and why
  // it cannot be used, and a workflow may still name it.
  const rolesResult = await listApproverRoles(true).then(
    (value) => ({ value, error: "" }),
    () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
  );

  const roles = rolesResult.value;
  const rolesError = rolesResult.error;

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
        {rolesError ? (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {rolesError}
          </div>
        ) : (
          <ApproverRoleTable roles={roles} assignments={{}} />
        )}
      </div>
    </div>
  );
}

export default RolesPage;
