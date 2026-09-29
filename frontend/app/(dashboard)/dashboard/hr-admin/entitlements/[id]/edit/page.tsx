import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { EntitlementForm } from "@/components/hr/entitlement-form";
import { getCurrentUser } from "@/lib/auth";
import { getEntitlement } from "@/lib/entitlements";

export default async function EditEntitlementPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let entitlement;
  try {
    entitlement = await getEntitlement(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/entitlements"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to entitlements
        </Link>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
          Edit entitlement
        </h2>
        <p className="text-text-secondary">
          Grade range {entitlement.grade_start} – {entitlement.grade_end},
          effective {entitlement.effective_from}.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <EntitlementForm
          entitlement={entitlement}
          endpoint={`/api/hr/entitlements/${entitlement.id}`}
          method="PATCH"
        />
      </div>
    </div>
  );
}