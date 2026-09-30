import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { loadPlanCapabilities } from "@/lib/plans/capabilities";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, capabilities, planCapabilities] = await Promise.all([
    getCurrentUser(),
    loadApprovalCapabilities(),
    loadPlanCapabilities(),
  ]);
  if (!user) redirect("/login");

  // The sidebar's approver items are decided here, in parallel with the user
  // read, so they are right in the first paint. Reading them here also lets
  // `getCurrentUser` and `loadApprovalCapabilities` be shared with the page
  // beneath this layout instead of being fetched twice.
  return (
    <DashboardShell
      user={user}
      isApprover={capabilities?.is_approver ?? false}
      pendingApprovals={capabilities?.pending_count ?? 0}
      planPendingConfirmations={planCapabilities?.pending_confirmation_count ?? 0}
    >
      {children}
    </DashboardShell>
  );
}
