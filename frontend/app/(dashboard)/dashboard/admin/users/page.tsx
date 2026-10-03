import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { AdminUserTable } from "@/components/admin/admin-user-table";
import { listAdminUsers } from "@/lib/admin-users";
import { getCurrentUser } from "@/lib/auth";

/**
 * Superuser-only user management.
 *
 * This is the top of the provisioning chain: a deployment is bootstrapped with
 * one superuser (created outside the product), and every HR account that then
 * configures departments, roles, teams, and workflows is created here. Nothing
 * on this page is seeded.
 */
export default async function AdminUsersPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_superuser) redirect("/dashboard");

  const users = await listAdminUsers();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">
            HR Users
          </h2>
          <p className="text-text-secondary">
            Create and manage the accounts that administer leave.
          </p>
        </div>
        <Link
          href="/dashboard/admin/users/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          Create HR user
        </Link>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <AdminUserTable users={users} />
      </div>
    </div>
  );
}
