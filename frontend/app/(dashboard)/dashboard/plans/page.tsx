import { PlansWorkspace } from "@/components/plans/plans-workspace";
import { getCurrentUser } from "@/lib/auth";
import { loadPlanCapabilities } from "@/lib/plans/capabilities";

const HR_ROLE = "hr";

/**
 * The plans workspace.
 *
 * Both answers come from the server, in parallel: "To decide" needs the caller
 * to be in the plans approver audience, and "All plans" is HR-only. The
 * approver answer is a data question — an approver position is held as a team
 * membership — while HR is the system role, so the two are read from their
 * own sources rather than one being inferred from the other. Both reads are
 * memoised per request, so the dashboard layout's own reads are shared.
 */
export default async function PlansPage() {
  const [user, capabilities] = await Promise.all([
    getCurrentUser(),
    loadPlanCapabilities(),
  ]);

  return (
    <PlansWorkspace
      isHR={user?.role === HR_ROLE}
      isApprover={capabilities?.is_approver ?? false}
    />
  );
}
