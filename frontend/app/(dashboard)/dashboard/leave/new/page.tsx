import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";

export default async function NewLeavePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <DashboardShell user={user}>
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-text-primary">
            New Leave Application
          </h2>
          <p className="text-text-secondary text-sm">
            Fill in the details below to start your leave application.
          </p>
        </div>
        <LeaveApplicationForm mode="create" />
      </div>
    </DashboardShell>
  );
}
