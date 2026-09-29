import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ReassignmentForm } from "@/components/hr/reassignment-form";
import { getCurrentUser } from "@/lib/auth";
import { listEmployees } from "@/lib/employees";
import { listPendingApplications } from "@/lib/reassignments";

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
    employees = await listEmployees();
  } catch {
    employeesError = "Unable to load people for the approver list.";
  }

  return (
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
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {employeesError}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <ReassignmentForm
            application={application}
            employees={employees?.results ?? []}
          />
        </div>
      )}
    </div>
  );
}