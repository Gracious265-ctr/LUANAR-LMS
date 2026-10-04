import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AdminUserForm } from "@/components/admin/admin-user-form";
import { getAdminUser } from "@/lib/admin-users";
import { getCurrentUser } from "@/lib/auth";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function EditAdminUserPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_superuser) redirect("/dashboard");

  const { id } = await params;

  let managed;
  try {
    managed = await getAdminUser(id);
  } catch {
    notFound();
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <Link
            href="/dashboard/admin/users"
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to HR users
          </Link>
          <h2 className="mt-2 text-2xl font-bold text-text-primary">
            {managed.full_name || managed.email}
          </h2>
          <p className="text-text-secondary">
            Rename the account, reset its password, or deactivate it.
          </p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <AdminUserForm user={managed} />
        </div>
      </div>
    </FadeIn>
  );
}
