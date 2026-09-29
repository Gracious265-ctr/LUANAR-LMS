import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { DelegationForm } from "@/components/hr/delegation-form";
import { getCurrentUser } from "@/lib/auth";
import { listEmployees } from "@/lib/employees";

export default async function NewDelegationPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let employees;
  let employeesError = "";
  try {
    employees = await listEmployees();
  } catch {
    employeesError = "Unable to load people for the approver and delegate lists.";
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/delegations"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to delegations
        </Link>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
          New delegation request
        </h2>
        <p className="text-text-secondary">
          Record an approver&apos;s unavailability so a delegate can act for them.
          An optional nomination here is confirmed by HR on approval.
        </p>
      </div>

      {employeesError ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {employeesError}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <DelegationForm employees={employees?.results ?? []} />
        </div>
      )}
    </div>
  );
}