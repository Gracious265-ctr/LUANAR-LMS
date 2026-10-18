import { notFound, redirect } from "next/navigation";

import { DelegationReview } from "@/components/hr/delegation-review";
import { COVER_BASE_HREF } from "@/components/approvals/cover-panel";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { canRequestCover, getDelegation } from "@/lib/delegations";
import { FadeIn } from "@/components/motion/FadeIn";

export const metadata = {
  title: "Delegation",
};

/**
 * An approver's read-only view of a delegation they are a party to.
 *
 * `getDelegation` is scoped by the API to the caller's own rows, so somebody
 * else's delegation is a 404 here rather than a page that renders someone
 * else's leave cover. HR keeps its own review page with the decision controls.
 */
export default async function CoverDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  if (!canRequestCover(await loadApprovalCapabilities())) {
    redirect("/");
  }

  const { id } = await params;
  const delegation = await getDelegation(id).catch(() => null);

  if (!delegation) {
    notFound();
  }

  return (
    <FadeIn>
      <DelegationReview
        delegation={delegation}
        employees={[]}
        readOnly
        backHref={COVER_BASE_HREF}
        title="Delegation"
      />
    </FadeIn>
  );
}
