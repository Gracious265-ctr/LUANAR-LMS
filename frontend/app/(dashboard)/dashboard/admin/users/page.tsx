import { redirect } from "next/navigation";

import { AdminUsersSection } from "@/components/admin/AdminUsersSection";
import { listAdminUsers } from "@/lib/admin-users";
import { getCurrentUser } from "@/lib/auth";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * Superuser-only user management.
 *
 * This is the top of the provisioning chain: a deployment is bootstrapped with
 * one superuser (created outside the product), and every HR account that then
 * configures departments, roles, teams, and workflows is created here. Nothing
 * on this page is seeded. Create and edit happen in an overlay on this list;
 * the old `new` and `[id]/edit` routes redirect here.
 */
export default async function AdminUsersPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_superuser) redirect("/dashboard");

  const users = await listAdminUsers();

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">
            HR Users
          </h2>
          <p className="text-text-secondary">
            Create and manage the accounts that administer leave.
          </p>
        </div>

        <AdminUsersSection users={users} />
      </div>
    </FadeIn>
  );
}
