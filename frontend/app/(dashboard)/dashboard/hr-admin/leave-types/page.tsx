import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { LeaveTypeTable } from "@/components/hr/leave-type-table";
import { getCurrentUser } from "@/lib/auth";
import { listLeaveTypes } from "@/lib/leave-rules";

export default async function LeaveTypesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let leaveTypes;
  let listError = "";
  try {
    leaveTypes = await listLeaveTypes();
  } catch {
    listError = "Unable to load leave types. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Leave types</h2>
          <p className="text-text-secondary">
            Manage the registry of leave types the university offers. Leave
            rules for each type are configured from the Leave Rules page.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/leave-types/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New leave type
        </Link>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Leave types
        </h3>
        {listError ? (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {listError}
          </div>
        ) : leaveTypes ? (
          <LeaveTypeTable leaveTypes={leaveTypes.results} />
        ) : null}
      </div>
    </div>
  );
}