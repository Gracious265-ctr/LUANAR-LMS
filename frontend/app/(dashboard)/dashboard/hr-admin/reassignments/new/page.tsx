import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ReassignmentForm } from "@/components/hr/reassignment-form";
import { getCurrentUser } from "@/lib/auth";
import { listAllEmployees } from "@/lib/employees";
import { listPendingApplications } from "@/lib/reassignments";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function NewReassignmentPage({
  searchParams,
}: {
  searchParams: Promise<{ application?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const params = await searchParams;
  const applicationId =
    typeof params.application === "string" ? params.application : "";

  if (!applicationId) {
    redirect("/dashboard/hr-admin/reassignments");
  }

  let pending;
  try {
    pending = await listPendingApplications();
  } catch {
    notFound();
  }
  const application = pending.results.find(
    (app) => app.id === applicationId
  );
  if (!application) {
    notFound();
  }

  let employees;
  let employeesError = "";
  try {
    // Whole list, not page one: a truncated picker would read to HR as
    // "nobody else can be chosen".
    employees = await listAllEmployees();
  } catch {
    employeesError = "Unable to load people for the approver list.";
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <Link
            href="/dashboard/hr-admin/reassignments"
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to reassignments
          </Link>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
            Reassign application
          </h2>
          <p className="text-text-secondary">
            Transfer a pending application to a replacement approver and record the
            mandatory reassignment reason.
          </p>
        </div>

        {employeesError ? (
          <Card>
            <div className="rounded-lg bg-status-rejected-subtle p-3 text-sm text-status-rejected">
              {employeesError}
            </div>
          </Card>
        ) : (
          <Card>
            <ReassignmentForm
              application={application}
              employees={employees ?? []}
            />
          </Card>
        )}
      </div>
    </FadeIn>
  );
}