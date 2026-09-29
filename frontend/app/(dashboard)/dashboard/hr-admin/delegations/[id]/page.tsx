import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { DelegationReview } from "@/components/hr/delegation-review";
import { getCurrentUser } from "@/lib/auth";
import { getDelegation } from "@/lib/delegations";
import { listEmployees } from "@/lib/employees";

export default async function DelegationDetailPage({
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

  let delegation;
  try {
    delegation = await getDelegation(id);
  } catch {
    notFound();
  }

  let employees;
  let employeesError = "";
  try {
    employees = await listEmployees();
  } catch {
    employeesError = "Unable to load people for the delegate list.";
  }

  return (
    <div className="space-y-6">
      {employeesError && (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <Link
            href="/dashboard/hr-admin/delegations"
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to delegations
          </Link>
          <div className="mt-4 rounded-lg bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {employeesError}
          </div>
        </div>
      )}
      {!employeesError && (
        <DelegationReview
          delegation={delegation}
          employees={employees?.results ?? []}
        />
      )}
    </div>
  );
}