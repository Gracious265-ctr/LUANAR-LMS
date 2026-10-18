import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { DelegationReview } from "@/components/hr/delegation-review";
import { getCurrentUser } from "@/lib/auth";
import { getDelegation } from "@/lib/delegations";
import { listAllEmployees } from "@/lib/employees";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

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
    // Whole list, not page one: a truncated picker would read to HR as
    // "nobody else can hold cover".
    employees = await listAllEmployees();
  } catch {
    employeesError = "Unable to load people for the delegate list.";
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        {employeesError && (
          <Card>
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
          </Card>
        )}
        {!employeesError && (
          <DelegationReview
            delegation={delegation}
            employees={employees ?? []}
          />
        )}
      </div>
    </FadeIn>
  );
}