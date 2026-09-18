import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";

export default async function EditLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { id } = await params;

  return (
    <DashboardShell user={user}>
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-text-primary">
            Edit Leave Application
          </h2>
          <p className="text-text-secondary text-sm">
            Update your leave application details.
          </p>
        </div>
        <LeaveApplicationForm mode="edit" applicationId={id} />
      </div>
    </DashboardShell>
  );
}
