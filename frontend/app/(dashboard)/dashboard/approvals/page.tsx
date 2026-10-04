import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { canRequestCover, loadCoverData } from "@/lib/delegations";
import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = {
  title: "Approvals",
};

export default async function ApprovalsPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string | string[] }>;
}) {
  // `searchParams` is independent of the capabilities read, so both are awaited
  // together. The cover data is only needed for an approver, and loading it
  // eagerly would fetch two more endpoints for somebody who cannot see it.
  const [capabilities, params] = await Promise.all([
    loadApprovalCapabilities(),
    searchParams,
  ]);
  const showCover = canRequestCover(capabilities);

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
    <FadeIn>
      <ApprovalsWorkspace
        canRequestCover
        initialView={initialView}
        delegations={delegations}
        candidates={candidates}
        delegationsError={error}
      />
    </FadeIn>
  );
}
