import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AdminUserForm } from "@/components/admin/admin-user-form";
import { getCurrentUser } from "@/lib/auth";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function NewAdminUserPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_superuser) redirect("/dashboard");

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
            New HR user
          </h2>
          <p className="text-text-secondary">
            Create an account that can administer leave. It is created with the
            Human Resources role and signs in with the email and password you set.
          </p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <AdminUserForm />
        </div>
      </div>
    </FadeIn>
  );
}
