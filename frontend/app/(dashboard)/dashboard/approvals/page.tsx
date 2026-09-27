import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import { getCurrentUser } from "@/lib/auth";
import { canRequestCover, loadCoverData } from "@/lib/delegations";

export const metadata = {
  title: "Approvals",
};

export default async function ApprovalsPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string | string[] }>;
}) {
  const user = await getCurrentUser();
  const showCover = canRequestCover(user?.role);

  const params = await searchParams;
  const requestedView = typeof params.view === "string" ? params.view : "";
  // Only an approver can be sent to the Cover tab; for anyone else the
  // parameter is ignored rather than trusted.
  const initialView =
    showCover && requestedView === "cover" ? "cover" : "applications";

  if (!showCover) {
    return <ApprovalsWorkspace />;
  }

  // Approver-only. Fetched here because the workspace is a client component
  // that owns the tab state; both reads are scoped to the caller by the API.
  const { delegations, candidates, error } = await loadCoverData();

  return (
    <ApprovalsWorkspace
      canRequestCover
      initialView={initialView}
      delegations={delegations}
      candidates={candidates}
      delegationsError={error}
    />
  );
}
