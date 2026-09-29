import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { EntitlementForm } from "@/components/hr/entitlement-form";
import { getCurrentUser } from "@/lib/auth";
import { Card } from "@/components/ui/card";

export default async function NewEntitlementPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
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
          New entitlement
        </h2>
        <p className="text-text-secondary">
          Define an annual leave entitlement for a grade range that is not
          already covered. To change an existing band, edit that rule instead.
        </p>
      </div>

      <Card>
        <EntitlementForm endpoint="/api/hr/entitlements" method="POST" />
      </Card>
    </div>
  );
}