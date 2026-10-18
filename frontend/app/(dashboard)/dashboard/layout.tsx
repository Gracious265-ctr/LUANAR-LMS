import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { loadPlanCapabilities } from "@/lib/plans/capabilities";

/**
 * The legacy `/dashboard/**` tree still renders the original floating-card
 * sidebar. The restructured module roots (`/leave`, `/approvals`, ...) render
 * their own `ModuleShell` from inside `(dashboard)/layout.tsx`, so the shell
 * that used to live on the group layout now lives here, scoped to the legacy
 * tree only.
 */
export default async function LegacyDashboardLayout({
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
