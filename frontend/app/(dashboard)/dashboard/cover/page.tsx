import { redirect } from "next/navigation";

import { CoverPanel } from "@/components/approvals/cover-panel";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { canRequestCover, loadCoverData } from "@/lib/delegations";
import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = {
  title: "Request Cover",
};

/**
 * The approver's own cover page, the target of the "Request Cover" sidebar item.
 *
 * Same panel as the Cover tab on /dashboard/approvals. It exists as its own
 * route so the sidebar can link straight to it and highlight it, which a
 * `?view=cover` query on the approvals page could not do.
 */
export default async function CoverPage() {
  if (!canRequestCover(await loadApprovalCapabilities())) {
    redirect("/dashboard");
  }

  const { delegations, candidates, error } = await loadCoverData();

  return (
    <FadeIn>
      <div className="space-y-6">
        <header>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">Request Cover</h1>
          <p className="mt-1 text-sm text-text-secondary">Nominate someone to handle your approvals while you are away.</p>
        </header>

        <CoverPanel
          delegations={delegations}
          candidates={candidates}
          error={error}
        />
      </div>
    </FadeIn>
  );
}
